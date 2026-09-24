"""E2E «тёмной»: рука закрыта по HTTP, открытие руки не крадёт время у соседа."""
import pytest

from tests.test_e2e_api import _auth, _login
from tests.test_rules_editions_api import _seed_edition

BLIND_CODE = "blind_test"
BLIND_CONFIG = {
    "rounds": {"mode": "custom", "sequence": [3]},
    "bidding": {"blind_allowed": True},
    "scoring": {"blind_bonus": 5},
}


async def _blind_room(client, n_players: int = 3):
    await _seed_edition(client, code=BLIND_CODE, config=BLIND_CONFIG, name="Тёмная")
    players = [await _login(client, f"BLIND_{i}") for i in range(n_players)]
    tokens = [t for t, _ in players]

    r = await client.post("/rooms", json={"rules_code": BLIND_CODE}, headers=_auth(tokens[0]))
    assert r.status_code == 200, r.text
    room_id, join_code = r.json()["room_id"], r.json()["join_code"]
    for t in tokens[1:]:
        assert (await client.post("/rooms/join", json={"join_code": join_code}, headers=_auth(t))).status_code == 200

    assert (await client.post(f"/rooms/{room_id}/start", headers=_auth(tokens[0]))).status_code == 200
    return room_id, tokens


async def _hand(client, room_id, token):
    r = await client.get(f"/rooms/{room_id}/hand", headers=_auth(token))
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_hand_stays_closed_until_opened(client):
    room_id, tokens = await _blind_room(client)
    before = await _hand(client, room_id, tokens[0])
    assert before["hand"] == [] and before["hand_hidden"] is True
    assert before["hand_count"] == 3 and before["can_open_hand"] is True

    r = await client.post(
        f"/rooms/{room_id}/action",
        json={"action_type": "open_hand", "payload": {}},
        headers=_auth(tokens[0]),
    )
    assert r.status_code == 200, r.text

    after = await _hand(client, room_id, tokens[0])
    assert len(after["hand"]) == 3 and after["hand_hidden"] is False


@pytest.mark.asyncio
async def test_opening_hand_does_not_extend_the_current_turn(client):
    """Иначе «открыть руку» превращается в бесплатную кнопку продления таймера."""
    room_id, tokens = await _blind_room(client)
    public = (await client.get(f"/rooms/{room_id}", headers=_auth(tokens[0]))).json()
    deadline = public["turn_deadline"]
    assert deadline is not None

    for token in tokens:
        await client.post(
            f"/rooms/{room_id}/action",
            json={"action_type": "open_hand", "payload": {}},
            headers=_auth(token),
        )

    after = (await client.get(f"/rooms/{room_id}", headers=_auth(tokens[0]))).json()
    assert after["turn_deadline"] == deadline
    assert after["turn"] == public["turn"]


@pytest.mark.asyncio
async def test_rules_view_exposes_blind_bonus(client):
    room_id, tokens = await _blind_room(client)
    rules = (await client.get(f"/rooms/{room_id}", headers=_auth(tokens[0]))).json()["rules"]
    assert rules["blind_bonus"] == 5


@pytest.mark.asyncio
async def test_open_hand_rejected_in_an_ordinary_edition(client):
    from tests.test_e2e_api import _make_room

    ctx = await _make_room(client, n_players=3)
    await client.post(f"/rooms/{ctx['room_id']}/start", headers=_auth(ctx["tokens"][0]))
    hand = await _hand(client, ctx["room_id"], ctx["tokens"][0])
    assert hand["hand_hidden"] is False and hand["can_open_hand"] is False

    r = await client.post(
        f"/rooms/{ctx['room_id']}/action",
        json={"action_type": "open_hand", "payload": {}},
        headers=_auth(ctx["tokens"][0]),
    )
    assert r.status_code == 409, r.text
