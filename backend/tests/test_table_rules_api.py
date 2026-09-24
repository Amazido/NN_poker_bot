"""E2E формы создания стола: заготовки, свои правила, отказы по негодным."""
import pytest

from app.poker.editions import BUILTIN_EDITIONS
from app.poker.rules_router import SEASON_EDITION_CODE
from tests.conftest import E2E_RULES_CODE
from tests.test_e2e_api import _auth, _login
from tests.test_rules_editions_api import _seed_edition

SEASON = next(e for e in BUILTIN_EDITIONS if e["code"] == SEASON_EDITION_CODE)

FORM = {
    "rounds_start": 2,
    "rounds_peak": 4,
    "two_beats_ace": True,
    "offcolor_beats_oncolor": False,
    "blind_allowed": True,
    "blind_bonus": 7,
    "infinite_deck": False,
    "pass_reward": 15,
    "trick_reward": 20,
    "overtrick_penalty": 3,
    "undertrick_penalty": 8,
}


async def _create(client, token, **body):
    return await client.post("/rooms", json=body, headers=_auth(token))


# === Заготовки для формы ===

@pytest.mark.asyncio
async def test_presets_offer_the_season_and_skip_inexpressible_editions(client):
    await _seed_edition(client, code=SEASON_EDITION_CODE, config=SEASON["config"], name="Сезон 1")
    r = await client.get("/rules/presets")
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["season"]["code"] == SEASON_EDITION_CODE
    assert data["season"]["settings"]["blind_allowed"] is True
    assert data["season"]["settings"]["blind_bonus"] == 5
    # Короткая e2e-редакция задана своим списком раздач — формой не выражается.
    assert E2E_RULES_CODE not in {p["code"] for p in data["presets"]}
    assert SEASON_EDITION_CODE not in {p["code"] for p in data["presets"]}


@pytest.mark.asyncio
async def test_presets_report_deck_limits(client):
    limits = (await client.get("/rules/presets")).json()["limits"]
    assert limits["min_start"] == 1
    assert limits["max_peak_one_deck"] == 10
    assert limits["max_peak_infinite"] > limits["max_peak_one_deck"]


@pytest.mark.asyncio
async def test_preset_settings_survive_a_round_trip_through_room_creation(client):
    """Заготовка обязана создавать ровно тот стол, который показала в полях."""
    await _seed_edition(client, code="preset_src", config=SEASON["config"], name="Источник")
    preset = next(p for p in (await client.get("/rules/presets")).json()["presets"] if p["code"] == "preset_src")

    token, _ = await _login(client, "preset_user")
    by_form = (await _create(client, token, rules=preset["settings"])).json()
    by_code = (await _create(client, token, rules_code="preset_src")).json()
    assert by_form["rules"]["summary"] == by_code["rules"]["summary"]


# === Свои правила ===

@pytest.mark.asyncio
async def test_room_created_with_hand_built_rules(client):
    token, _ = await _login(client, "form_host")
    r = await _create(client, token, rules=FORM)
    assert r.status_code == 200, r.text

    rules = r.json()["rules"]
    assert rules["code"] == "custom"
    assert rules["blind_bonus"] == 7
    assert any("от 2 до 4 карт" in line for line in rules["summary"])
    assert any("+20 за взятку" in line and "-3 за перебор" in line for line in rules["summary"])


@pytest.mark.asyncio
async def test_hand_built_rules_survive_to_the_match(client):
    """Правила стола должны доехать до раздачи, а не потеряться на старте."""
    host, _ = await _login(client, "form_start_host")
    room = (await _create(client, host, rules={**FORM, "rounds_start": 3, "rounds_peak": 3})).json()
    room_id = room["room_id"]

    for i in range(2):
        t, _ = await _login(client, f"form_start_{i}")
        await client.post("/rooms/join", json={"join_code": room["join_code"]}, headers=_auth(t))

    started = (await client.post(f"/rooms/{room_id}/start", headers=_auth(host))).json()
    assert started["round"]["cards_count"] == 3
    assert started["rounds_total"] == 3  # только плато: пик равен первой раздаче
    assert started["rules"]["code"] == "custom"


@pytest.mark.asyncio
async def test_own_rules_win_over_edition_code(client):
    """Пришло и то и другое — играем по своим: их человек только что собрал."""
    token, _ = await _login(client, "both_host")
    r = await _create(client, token, rules_code=E2E_RULES_CODE, rules=FORM)
    assert r.json()["rules"]["code"] == "custom"


@pytest.mark.asyncio
async def test_rules_code_still_works_without_a_form(client):
    """Галочка «правила сезона» шлёт только код — этот путь ломать нельзя."""
    token, _ = await _login(client, "code_host")
    r = await _create(client, token, rules_code=E2E_RULES_CODE)
    assert r.status_code == 200, r.text
    assert r.json()["rules"]["code"] == E2E_RULES_CODE


# === Отказы ===

@pytest.mark.asyncio
async def test_hand_built_rules_rejected_when_hand_does_not_fit_the_deck(client):
    token, _ = await _login(client, "too_big_host")
    r = await _create(client, token, rules={**FORM, "rounds_peak": 13})
    assert r.status_code == 409, r.text
    assert "не влезает" in r.json()["detail"]


@pytest.mark.asyncio
async def test_same_hand_size_allowed_with_an_infinite_deck(client):
    token, _ = await _login(client, "big_infinite_host")
    r = await _create(client, token, rules={**FORM, "rounds_peak": 13, "infinite_deck": True})
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_peak_below_start_rejected(client):
    token, _ = await _login(client, "backwards_host")
    r = await _create(client, token, rules={**FORM, "rounds_start": 6, "rounds_peak": 2})
    assert r.status_code == 409, r.text


@pytest.mark.asyncio
async def test_negative_numbers_rejected_by_the_schema(client):
    token, _ = await _login(client, "negative_host")
    r = await _create(client, token, rules={**FORM, "rounds_start": 0})
    assert r.status_code == 422, r.text
