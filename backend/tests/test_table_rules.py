"""Свои правила стола: сборка конфига из полей формы и заготовки для неё."""
import random

import pytest

from app.poker import engine
from app.poker.autoplay import choose_auto_action
from app.poker.editions import BUILTIN_EDITIONS
from app.poker.rules import (
    MAX_PEAK_INFINITE,
    RulesConfigError,
    RulesEdition,
    config_from_settings,
    max_peak_finite,
    settings_from_config,
)

BASE = {
    "rounds_start": 1,
    "rounds_peak": 5,
    "two_beats_ace": False,
    "offcolor_beats_oncolor": False,
    "blind_allowed": False,
    "blind_bonus": 0,
    "infinite_deck": False,
    "pass_reward": 10,
    "trick_reward": 10,
    "overtrick_penalty": 5,
    "undertrick_penalty": 10,
}


def _settings(**over):
    return {**BASE, **over}


# === Поля формы → конфиг ===

def test_penalties_are_entered_positive_and_stored_negative():
    """Игрок пишет «штраф 5», в конфиге это −5 — знак ставит сервер."""
    scoring = config_from_settings(_settings(overtrick_penalty=7, undertrick_penalty=3))["scoring"]
    assert scoring["over"] == -7
    assert scoring["under_per_trick"] == -3


def test_penalty_sign_is_forgiving():
    """Если знак всё же прислали, минус не станет плюсом."""
    scoring = config_from_settings(_settings(overtrick_penalty=-7))["scoring"]
    assert scoring["over"] == -7


def test_blind_bonus_ignored_when_blind_is_off():
    """Иначе выключенная галочка оставила бы за собой висящую надбавку."""
    cfg = config_from_settings(_settings(blind_allowed=False, blind_bonus=5))
    assert cfg["scoring"]["blind_bonus"] == 0
    assert cfg["bidding"]["blind_allowed"] is False


def test_form_config_is_playable():
    rules = RulesEdition(config_from_settings(_settings(rounds_start=2, rounds_peak=6)), validate=True)
    assert rules.round_sequence(4) == [2, 3, 4, 5, 6, 6, 6, 6, 5, 4, 3, 2]


def test_infinite_deck_unlocks_bigger_hands():
    """Одна колода 15 карт на пятерых не даёт, безлимитная — даёт."""
    with pytest.raises(RulesConfigError):
        RulesEdition(config_from_settings(_settings(rounds_peak=15)), validate=True)
    RulesEdition(config_from_settings(_settings(rounds_peak=15, infinite_deck=True)), validate=True)


def test_peak_below_start_is_rejected():
    with pytest.raises(RulesConfigError):
        RulesEdition(config_from_settings(_settings(rounds_start=6, rounds_peak=3)), validate=True)


def test_form_limits_match_the_deck():
    """Потолок формы обязан совпадать с тем, что реально влезает в колоду."""
    peak = max_peak_finite()
    RulesEdition(config_from_settings(_settings(rounds_peak=peak)), validate=True)
    with pytest.raises(RulesConfigError):
        RulesEdition(config_from_settings(_settings(rounds_peak=peak + 1)), validate=True)
    RulesEdition(
        config_from_settings(_settings(rounds_peak=MAX_PEAK_INFINITE, infinite_deck=True)), validate=True
    )


# === Конфиг → поля формы ===

def test_settings_roundtrip():
    settings = _settings(rounds_peak=7, two_beats_ace=True, blind_allowed=True, blind_bonus=5)
    assert settings_from_config(config_from_settings(settings)) == settings


@pytest.mark.parametrize("spec", BUILTIN_EDITIONS, ids=lambda s: s["code"])
def test_builtin_edition_is_either_a_faithful_preset_or_no_preset(spec):
    """Заготовка обязана заполнять форму ровно тем, что написано на кнопке.

    Редакции, которые форма не выражает, должны отсеиваться, а не подставлять
    похожие значения: «Блиц» без плато превратился бы в матч вдвое длиннее.
    """
    settings = settings_from_config(spec["config"])
    if settings is None:
        return
    assert RulesEdition(config_from_settings(settings)).config == RulesEdition(spec["config"]).config


def test_editions_the_form_cannot_express_are_not_presets():
    by_code = {e["code"]: e["config"] for e in BUILTIN_EDITIONS}
    # Блиц играется без плато на пике, «Глубокая» сажает максимум четверых —
    # ни то, ни другое форма не спрашивает.
    assert settings_from_config(by_code["odessa_blitz"]) is None
    assert settings_from_config(by_code["odessa_deep"]) is None
    assert settings_from_config(by_code["odessa_season_1"]) is not None


def test_season_preset_matches_the_reference_edition():
    season = next(e for e in BUILTIN_EDITIONS if e["code"] == "odessa_season_1")
    assert settings_from_config(season["config"]) == {
        "rounds_start": 1,
        "rounds_peak": 10,
        "two_beats_ace": True,
        "offcolor_beats_oncolor": True,
        "blind_allowed": True,
        "blind_bonus": 5,
        "infinite_deck": False,
        "pass_reward": 10,
        "trick_reward": 10,
        "overtrick_penalty": 5,
        "undertrick_penalty": 5,
    }


# === Игра по собранным правилам ===

def test_bots_play_a_full_match_on_hand_built_rules():
    """Собранные в форме правила должны быть играбельны, а не только валидны."""
    config = config_from_settings(
        _settings(rounds_start=2, rounds_peak=4, two_beats_ace=True, blind_allowed=True,
                  blind_bonus=5, infinite_deck=True)
    )
    rng = random.Random(3)
    state = engine.new_game_state(
        room_id="r",
        seats=[{"seat": i, "user_id": f"u{i}", "username": f"P{i}", "score": 0} for i in range(4)],
        rules_config=config,
        starting_dealer=0,
        rng=rng,
    )
    guard = 0
    while not state["match_over"]:
        guard += 1
        assert guard < 20000, "матч не сходится"
        seat, action_type, payload = choose_auto_action(state)
        engine.apply_action(state, seat, action_type, payload, rng)

    assert state["round_index"] == len(RulesEdition(config).round_sequence(4))
