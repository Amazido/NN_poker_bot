"""Встроенный каталог редакций правил.

Редакции сидятся при старте приложения (`main.ensure_builtin_rules`) и вручную
(`scripts.seed_rules`). Уже существующая в БД редакция не трогается: у неё может
быть своя история комнат, а конфиг мог быть отредактирован руками.

Правки правил выпускаются **новой версией**, а не изменением существующей, —
иначе поменяется смысл уже сыгранных матчей, которые на неё ссылаются.
"""
from typing import Any, Dict, List

BUILTIN_EDITIONS: List[Dict[str, Any]] = [
    {
        "code": "odessa_classic",
        "version": 1,
        "name": "Классическая",
        "description": (
            "Базовый Одесский покер: колода 54, раздачи от 1 до 10 карт, "
            "крюк у сдающего, джокеры по цвету козыря."
        ),
        "config": {},  # чистые дефолты
    },
    {
        "code": "odessa_circular",
        "version": 1,
        "name": "Круговое старшинство",
        "description": (
            "Младшее бьёт старшее: двойка забирает туза своей масти, "
            "а некозырной джокер — козырного."
        ),
        "config": {
            "ranking": {
                "two_beats_ace_same_suit": True,
                "offcolor_beats_oncolor": True,
            },
        },
    },
    {
        "code": "odessa_blitz",
        "version": 1,
        "name": "Блиц",
        "description": "Короткий матч на 9 раздач: от 1 до 5 карт и обратно, без плато.",
        "config": {
            "rounds": {"mode": "up_down", "start": 1, "peak": 5},
        },
    },
    {
        "code": "odessa_deep",
        "version": 1,
        "name": "Глубокая раздача",
        "description": (
            "Крупные руки: раздачи от 5 до 13 карт. Максимум четверо за столом — "
            "на пятерых колоды уже не хватит."
        ),
        "config": {
            "players": {"min": 3, "max": 4},
            "rounds": {"mode": "up_plateau_down", "start": 5, "peak": 13},
        },
    },
    {
        "code": "odessa_infinite",
        "version": 1,
        "name": "Безлимитная колода",
        "description": (
            "Каждая карта тянется заново, поэтому одинаковые карты встречаются "
            "и в одной руке, и у разных игроков. При равных берёт тот, кто "
            "положил раньше. Размер раздачи колодой не ограничен."
        ),
        "config": {
            "deck": {"infinite": True},
            "ranking": {"duplicate_first_wins": True},
        },
    },
    {
        # Эталон первого сезона. На неё будут ссылаться рейтинг и награды, поэтому
        # конфиг фиксируется здесь целиком, а не собирается из дефолтов.
        "code": "odessa_season_1",
        "version": 1,
        "name": "Сезон 1",
        "description": (
            "Эталонные правила первого сезона: одна колода, последовательный "
            "заказ с крюком, двойка бьёт туза своей масти, некозырной джокер "
            "бьёт козырного. Можно заказать вслепую и получить +5 за точный заказ."
        ),
        "config": {
            "deck": {"jokers": 2, "infinite": False},
            "ranking": {
                "two_beats_ace_same_suit": True,
                "offcolor_beats_oncolor": True,
                "duplicate_first_wins": True,
            },
            "bidding": {"hook": True, "blind_allowed": True},
            "scoring": {
                "exact_per_trick": 10,
                "exact_zero_bonus": 10,
                "over": -5,
                "under_per_trick": -5,
                "blind_bonus": 5,
            },
        },
    },
]
