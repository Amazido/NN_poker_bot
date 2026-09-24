"""Редакция правил: конфиг варианта, последовательность раздач, подсчёт очков.

Конфиг лежит в `rules_editions.config` (JSONB) и целиком копируется в состояние
матча при старте (`engine.new_game_state`) — правка редакции не меняет правила
уже идущих матчей.

`RulesEdition` — тонкая обёртка над dict: подставляет дефолты, поднимает конфиги
старой схемы до текущей и отвечает на вопросы движка. Проверка «по этому конфигу
вообще можно играть» вынесена в `validate()` и вызывается только при заведении
редакции и создании стола: снапшот правил идущего матча обязан читаться всегда,
даже если редакцию потом признали негодной.
"""
import copy
from typing import Any, Dict, List, Optional

from app.poker.cards import deck_size

SCHEMA_VERSION = 2

ROUND_MODES = ("up_plateau_down", "up_down", "custom")

# Дефолтная редакция «odessa_classic».
DEFAULT_CONFIG: Dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    # infinite: карты тянутся независимо, повторы возможны, раздача не ограничена
    # размером колоды.
    "deck": {"jokers": 2, "infinite": False},
    "players": {"min": 3, "max": 5},
    # up_plateau_down: start..peak-1, затем peak повторяется n раз (каждый игрок
    # сдаёт «пик» по разу), затем peak-1..start. При start=1, peak=10 это 18+n раздач.
    "rounds": {"mode": "up_plateau_down", "start": 1, "peak": 10, "sequence": None},
    "ranking": {
        "two_beats_ace_same_suit": False,
        "offcolor_beats_oncolor": False,
        "duplicate_first_wins": True,
    },
    # blind_allowed: можно заказать, не открывая руку («тёмная»).
    "bidding": {"hook": True, "blind_allowed": False},
    "scoring": {
        "exact_per_trick": 10,   # точный заказ: +10 за каждую взятку
        "exact_zero_bonus": 10,  # заказал 0 и взял 0: фикс +10
        "over": -5,              # перебор: фикс -5
        "under_per_trick": -10,  # недобор: -10 за каждую недобранную
        "blind_bonus": 0,        # надбавка за точный заказ, сделанный вслепую
    },
    "turn_timeout_sec": 30,
}


class RulesConfigError(ValueError):
    """По этому конфигу нельзя играть."""


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _upgrade(config: Dict[str, Any]) -> Dict[str, Any]:
    """Поднять конфиг до текущей схемы.

    Редакции схемы v1 лежат в БД, а снапшоты правил идущих матчей — в Redis,
    поэтому читать v1 нужно уметь бессрочно, а не до ближайшего деплоя.
    """
    cfg = copy.deepcopy(config)
    if int(cfg.get("schema_version", 1)) >= 2:
        return cfg

    # v1: флаги старшинства жили в блоке "jokers" (переехали в "ranking"),
    # а deck.cards дублировал размер колоды, который выводится из числа джокеров.
    legacy = cfg.pop("jokers", None)
    if isinstance(legacy, dict):
        ranking = dict(cfg.get("ranking") or {})
        for key in ("two_beats_ace_same_suit", "offcolor_beats_oncolor"):
            if key in legacy:
                ranking.setdefault(key, bool(legacy[key]))
        cfg["ranking"] = ranking

    deck = dict(cfg.get("deck") or {})
    deck.pop("cards", None)
    cfg["deck"] = deck

    cfg["schema_version"] = SCHEMA_VERSION
    return cfg


class RulesEdition:
    """Обёртка над config редакции с дефолтами и удобными аксессорами."""

    def __init__(self, config: Optional[Dict[str, Any]] = None, *, validate: bool = False):
        self.config = _deep_merge(DEFAULT_CONFIG, _upgrade(config or {}))
        if validate:
            self.validate()

    # --- Колода ---
    @property
    def jokers_count(self) -> int:
        return int(self.config["deck"]["jokers"])

    @property
    def deck_size(self) -> int:
        return deck_size(self.jokers_count)

    @property
    def infinite_deck(self) -> bool:
        return bool(self.config["deck"]["infinite"])

    # --- Игроки ---
    @property
    def min_players(self) -> int:
        return int(self.config["players"]["min"])

    @property
    def max_players(self) -> int:
        return int(self.config["players"]["max"])

    # --- Старшинство ---
    @property
    def ranking(self) -> Dict[str, bool]:
        return {k: bool(v) for k, v in self.config["ranking"].items()}

    # --- Торги ---
    @property
    def hook_enabled(self) -> bool:
        return bool(self.config["bidding"]["hook"])

    @property
    def blind_allowed(self) -> bool:
        return bool(self.config["bidding"]["blind_allowed"])

    @property
    def turn_timeout_sec(self) -> int:
        return int(self.config["turn_timeout_sec"])

    # --- Последовательность раздач ---
    # Безлимитная колода снимает ограничение на размер руки, но рука больше
    # колоды не нужна никому и ломает раскладку стола.
    MAX_HAND_SANITY = 52

    def max_cards_per_hand(self, n_players: int) -> int:
        """Сколько карт максимум влезает в раздачу: одна уходит на козырь."""
        if self.infinite_deck:
            return self.MAX_HAND_SANITY
        return (self.deck_size - 1) // n_players

    def round_sequence(self, n_players: int) -> List[int]:
        """Список длин раздач (карт на игрока) для матча из n_players.

        Не влезающую в колоду раздачу раньше молча урезали — «13 карт на пятерых»
        тихо превращались в 10. Теперь это ошибка конфига.
        """
        rounds = self.config["rounds"]
        mode = rounds.get("mode", "up_plateau_down")
        start = int(rounds.get("start", 1))

        if mode == "custom":
            seq = [int(x) for x in (rounds.get("sequence") or [])]
        elif mode == "up_plateau_down":
            peak = int(rounds["peak"])
            seq = (
                list(range(start, peak))
                + [peak] * n_players
                + list(range(peak - 1, start - 1, -1))
            )
        elif mode == "up_down":
            peak = int(rounds["peak"])
            seq = list(range(start, peak + 1)) + list(range(peak - 1, start - 1, -1))
        else:
            raise RulesConfigError(f"rounds.mode: {mode!r}, допустимо {list(ROUND_MODES)}")

        if not seq or any(c < 1 for c in seq):
            raise RulesConfigError("rounds: последовательность пуста или содержит непозитивные числа")

        limit = self.max_cards_per_hand(n_players)
        biggest = max(seq)
        if biggest > limit:
            if self.infinite_deck:
                raise RulesConfigError(
                    f"Раздача {biggest} карт — слишком много даже для безлимитной "
                    f"колоды (потолок {limit})"
                )
            raise RulesConfigError(
                f"Раздача {biggest} карт на {n_players} игроков не влезает в колоду: "
                f"максимум {limit} (колода {self.deck_size}, одна карта уходит на козырь)"
            )
        return seq

    # --- Подсчёт очков раздачи ---
    def score(self, bid: int, tricks_won: int, blind: bool = False) -> int:
        """Очки за раздачу.

        Надбавка за слепой заказ идёт только при попадании; при промахе минусы
        начисляются в полном объёме, без скидок за риск.
        """
        s = self.config["scoring"]
        if tricks_won == bid:
            base = int(s["exact_zero_bonus"]) if bid == 0 else int(s["exact_per_trick"]) * tricks_won
            return base + (int(s["blind_bonus"]) if blind else 0)
        if tricks_won > bid:
            return int(s["over"])
        return int(s["under_per_trick"]) * (bid - tricks_won)

    # --- Ограничение «крюка» на торгах ---
    def forbidden_last_bid(self, cards_count: int, others_bid_sum: int) -> Optional[int]:
        """Запрещённый заказ для последнего в очереди (сдающего).

        Нельзя сделать сумму заказов равной числу карт в раздаче.
        """
        if not self.hook_enabled:
            return None
        value = cards_count - others_bid_sum
        if 0 <= value <= cards_count:
            return value
        return None

    def allowed_bids(
        self, cards_count: int, is_last_bidder: bool, others_bid_sum: int
    ) -> List[int]:
        """Доступные значения заказа для игрока."""
        options = list(range(0, cards_count + 1))
        if is_last_bidder:
            forbidden = self.forbidden_last_bid(cards_count, others_bid_sum)
            if forbidden is not None:
                options = [b for b in options if b != forbidden]
        return options

    # --- Проверка конфига ---
    def validate(self) -> None:
        """Убедиться, что по конфигу можно играть. Бросает RulesConfigError."""
        cfg = self.config
        self._check_unknown_keys()

        if int(cfg["schema_version"]) != SCHEMA_VERSION:
            raise RulesConfigError(
                f"schema_version {cfg['schema_version']}, поддерживается {SCHEMA_VERSION}"
            )

        if self.jokers_count not in (0, 2):
            raise RulesConfigError("deck.jokers: поддерживается 0 или 2 джокера")

        if self.min_players < 2 or self.max_players < self.min_players:
            raise RulesConfigError(
                f"players: нужно 2 <= min <= max, получено {self.min_players}..{self.max_players}"
            )

        rounds = cfg["rounds"]
        mode = rounds.get("mode")
        if mode not in ROUND_MODES:
            raise RulesConfigError(f"rounds.mode: {mode!r}, допустимо {list(ROUND_MODES)}")
        if mode == "custom":
            if not (rounds.get("sequence") or []):
                raise RulesConfigError("rounds.sequence: при mode=custom нужен непустой список")
        else:
            start, peak = int(rounds.get("start", 1)), int(rounds["peak"])
            if start < 1:
                raise RulesConfigError("rounds.start: должен быть >= 1")
            if peak < start:
                raise RulesConfigError(f"rounds.peak ({peak}) меньше rounds.start ({start})")

        if self.turn_timeout_sec < 5:
            raise RulesConfigError("turn_timeout_sec: должен быть >= 5")

        # Раздача должна влезать в колоду при любом допустимом числе игроков —
        # иначе матч упадёт на середине, когда дойдёт до большой раздачи.
        for n in range(self.min_players, self.max_players + 1):
            self.round_sequence(n)

    def _check_unknown_keys(self) -> None:
        """Опечатка в ключе иначе молча растворится в дефолтах."""
        unknown = set(self.config) - set(DEFAULT_CONFIG)
        if unknown:
            raise RulesConfigError(f"неизвестные ключи конфига: {sorted(unknown)}")
        for block, defaults in DEFAULT_CONFIG.items():
            if not isinstance(defaults, dict):
                continue
            extra = set(self.config.get(block) or {}) - set(defaults)
            if extra:
                raise RulesConfigError(f"неизвестные ключи в блоке {block}: {sorted(extra)}")

    # --- Человекочитаемое описание (для выбора редакции на фронте) ---
    def summary(self) -> List[str]:
        """Чем эта редакция отличается от классики — короткими фразами."""
        out: List[str] = []
        rounds = self.config["rounds"]
        if rounds.get("mode") == "custom":
            seq = rounds.get("sequence") or []
            out.append(f"Раздачи: {', '.join(str(c) for c in seq)}")
        else:
            start, peak = int(rounds.get("start", 1)), int(rounds["peak"])
            out.append(f"Раздачи от {start} до {peak} карт")

        out.append(f"Игроков {self.min_players}–{self.max_players}")

        if self.infinite_deck:
            first = "раньше" if self.ranking.get("duplicate_first_wins", True) else "позже"
            out.append(f"Безлимитная колода: карты повторяются, при равных берёт положивший {first}")
        if self.jokers_count == 0:
            out.append("Без джокеров")
        if self.ranking.get("two_beats_ace_same_suit"):
            out.append("Двойка бьёт туза своей масти")
        if self.ranking.get("offcolor_beats_oncolor"):
            out.append("Некозырной джокер бьёт козырного")
        if not self.hook_enabled:
            out.append("Без «крюка» у сдающего")

        s = self.config["scoring"]
        if self.blind_allowed:
            out.append(f"Можно заказать вслепую: +{s['blind_bonus']} за точный заказ")
        out.append(
            f"Очки: +{s['exact_per_trick']} за взятку при точном заказе, "
            f"{s['over']} за перебор, {s['under_per_trick']} за недобранную"
        )
        return out
