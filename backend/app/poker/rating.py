"""Рейтинг сезона: места в матче, прибавки и отбор зачётных матчей.

Здесь только чистые функции над числами — ни БД, ни состояния матча. Так
формулу можно менять, не трогая запись результатов: сами результаты матчей
(`matches`, `match_players`) собираются независимо от того, как мы их считаем,
а каждое изменение рейтинга лежит в журнале (`rating_events`) вместе с
рейтингом до и после. Пересчёт по новой формуле — это перезапись журнала, а не
правка чисел «на месте».

ВАЖНО: формула ниже — заведомо временная, первое касание. Её назначение —
начать собирать метрики (кто с каким рейтингом садился, чем кончилось,
рейтинговый ли был стол), чтобы по этим метрикам придумать настоящую.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional

# Рейтинг, с которого игрок входит в сезон.
INITIAL_RATING = 1000

# Сколько живых игроков нужно, чтобы матч пошёл в зачёт.
MIN_HUMAN_PLAYERS = 3


class UnratedReason:
    """Почему матч не пошёл в рейтинг. Храним причину, а не просто «нет»:
    по ней видно, чего в сезоне не хватает — столов по правилам лиги или людей."""

    NO_SEASON = "no_season"              # активного сезона не было
    HOUSE_RULES = "house_rules"          # стол играл не по редакции сезона
    BOTS = "bots"                        # за столом был бот
    TOO_FEW_PLAYERS = "too_few_players"  # живых игроков меньше минимума



def rating_deltas(n_players: int) -> List[int]:
    """Прибавки рейтинга по месту: индекс 0 — первое место.

    Шкала симметрична и в сумме даёт ноль: сколько рейтинга наверху прибыло,
    столько внизу убыло. При чётном числе игроков нуля в шкале нет — делить
    стол ровно пополам честнее, чем выдавать кому-то «ничью».

        3 игрока → +1, 0, −1
        4 игрока → +2, +1, −1, −2
        5 игроков → +2, +1, 0, −1, −2
    """
    half = n_players // 2
    if n_players % 2:
        return list(range(half, -half - 1, -1))
    return list(range(half, 0, -1)) + list(range(-1, -half - 1, -1))


def places_by_score(scores: Dict[int, int]) -> Dict[int, int]:
    """Места по счёту матча: {место игрока} по {место за столом: счёт}.

    Равный счёт — равное место (1, 2, 2, 4): ничья в Одесском покере вполне
    реальна, очки кратны пятёрке. Разводить её по порядку хода или по месту за
    столом было бы выдумкой — такого правила в игре нет.
    """
    return {
        seat: 1 + sum(1 for other in scores.values() if other > score)
        for seat, score in scores.items()
    }


def delta_for_place(place: int, n_players: int) -> int:
    """Прибавка за место без учёта ничьих."""
    deltas = rating_deltas(n_players)
    if not deltas:
        return 0
    return deltas[min(max(place, 1), len(deltas)) - 1]


def deltas_by_seat(places: Dict[int, int], n_players: int) -> Dict[int, int]:
    """Прибавки по местам за столом с учётом поделённых мест.

    Поделившие место делят и прибавки за занятые ими позиции шкалы: трое с
    равным счётом из трёх получают среднее от (+1, 0, −1), то есть ноль, а не
    по +1 каждому. Иначе ничья печатала бы рейтинг из ничего.

    Среднее округляется вниз, поэтому при ничьей сумма по столу может оказаться
    чуть меньше нуля, но никогда больше: рейтинг от ничьих не растёт.
    """
    scale = rating_deltas(n_players)
    groups: Dict[int, List[int]] = {}
    for seat, place in places.items():
        groups.setdefault(place, []).append(seat)

    out: Dict[int, int] = {}
    for place, seats in groups.items():
        # Группа из k игроков на месте `place` занимает позиции place..place+k-1.
        chunk = [
            scale[i] for i in range(place - 1, place - 1 + len(seats)) if 0 <= i < len(scale)
        ]
        share = sum(chunk) // len(chunk) if chunk else 0
        for seat in seats:
            out[seat] = share
    return out


@dataclass(frozen=True)
class Eligibility:
    """Пошёл ли матч в рейтинг и почему нет."""

    rated: bool
    reason: Optional[str] = None


def eligibility(
    *,
    season_edition_id: Optional[str],
    room_edition_id: Optional[str],
    human_players: int,
    bot_players: int,
    min_humans: int = MIN_HUMAN_PLAYERS,
) -> Eligibility:
    """Зачётный ли матч.

    Проверки идут от общего к частному, и запоминается первая несработавшая:
    «сезона нет» объясняет больше, чем «мало людей», если верно и то и другое.

    `room_edition_id is None` — это стол со своими правилами (у комнаты
    заполнен `rules_config`): по признаку создания, а не по совпадению конфига,
    иначе случайно совпавший набор галочек попадал бы в зачёт сезона.
    """
    if not season_edition_id:
        return Eligibility(False, UnratedReason.NO_SEASON)
    if room_edition_id != season_edition_id:
        return Eligibility(False, UnratedReason.HOUSE_RULES)
    # Бот за столом отменяет зачёт целиком, а не «считается за игрока»: его ход
    # выбирает авто-ход, и рейтинг живых игроков об этом ничего не знает.
    if bot_players > 0:
        return Eligibility(False, UnratedReason.BOTS)
    if human_players < min_humans:
        return Eligibility(False, UnratedReason.TOO_FEW_PLAYERS)
    return Eligibility(True)
