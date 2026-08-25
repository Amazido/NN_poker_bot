"""Выход из комнаты: изоляция личного канала и закрытие брошенного матча.

Личный канал `user#{id}` один на человека и переживает смену комнаты, поэтому
покинутый матч не должен ни слать в него свою руку, ни доигрываться авто-ходом
в пустоту — иначе он перебивает состояние комнаты, открытой сейчас.
"""
import pytest

from app.core.centrifugo import ch_user
from tests.conftest import E2E_RULES_CODE
from tests.test_e2e_api import _auth, _login, _make_room


@pytest.fixture
def published(monkeypatch) -> list:
    """Перехват публикаций в Centrifugo: список (channel, data)."""
    records: list = []

    async def _rec(channel, data):
        records.append((channel, data))

    monkeypatch.setattr("app.poker.channels.safe_publish", _rec)
    return records


def _privates_for(records: list, user_id: str) -> list:
    return [d["private"] for c, d in records if c == ch_user(user_id) and d.get("type") == "private"]


@pytest.mark.asyncio
async def test_private_view_carries_room_id(client):
    """Приватный вид говорит, к какой комнате он относится."""
    ctx = await _make_room(client, 3)
    room_id, tokens = ctx["room_id"], ctx["tokens"]
    await client.post(f"/rooms/{room_id}/start", headers=_auth(tokens[0]))

    hand = (await client.get(f"/rooms/{room_id}/hand", headers=_auth(tokens[0]))).json()
    assert hand["room_id"] == room_id


@pytest.mark.asyncio
async def test_left_player_gets_no_private_updates(client, published):
    """Ушедшему приватку больше не шлём, остальным за столом — шлём."""
    ctx = await _make_room(client, 3)
    room_id, tokens, user_ids = ctx["room_id"], ctx["tokens"], ctx["user_ids"]
    await client.post(f"/rooms/{room_id}/start", headers=_auth(tokens[0]))

    published.clear()
    r = await client.post(f"/rooms/{room_id}/leave", headers=_auth(tokens[1]))
    assert r.status_code == 200, r.text

    assert _privates_for(published, user_ids[1]) == [], "ушедший продолжает получать руку"
    for uid in (user_ids[0], user_ids[2]):
        assert _privates_for(published, uid), f"игрок за столом {uid} остался без обновления"

    # И каждая приватка помечена своей комнатой — по этому полю клиент отсеивает чужое.
    for uid in (user_ids[0], user_ids[2]):
        assert all(p["room_id"] == room_id for p in _privates_for(published, uid))


@pytest.mark.asyncio
async def test_match_closes_when_everyone_left(client):
    """Уходит последний живой игрок — матч закрывается, а не доигрывается в пустоту."""
    ctx = await _make_room(client, 3)
    room_id, tokens = ctx["room_id"], ctx["tokens"]
    await client.post(f"/rooms/{room_id}/start", headers=_auth(tokens[0]))

    for t in tokens[:2]:
        await client.post(f"/rooms/{room_id}/leave", headers=_auth(t))
    mid = (await client.get(f"/rooms/{room_id}", headers=_auth(tokens[2]))).json()
    assert mid["match_over"] is False, "матч закрылся, пока за столом ещё кто-то есть"

    last = await client.post(f"/rooms/{room_id}/leave", headers=_auth(tokens[2]))
    assert last.status_code == 200, last.text

    pub = (await client.get(f"/rooms/{room_id}", headers=_auth(tokens[0]))).json()
    assert pub["match_over"] is True
    assert pub["turn"]["kind"] is None
    assert pub["turn_deadline"] is None

    from app.poker import state as state_store

    assert room_id not in await state_store.list_active_rooms(), "комната осталась под авто-ходом"


@pytest.mark.asyncio
async def test_match_with_only_bots_left_closes(client):
    """Хост ушёл из стола с ботами — доигрывать некому, матч закрывается."""
    token, _ = await _login(client, "bots_host")
    room = (await client.post("/rooms", json={"rules_code": E2E_RULES_CODE}, headers=_auth(token))).json()
    room_id = room["room_id"]
    for _ in range(2):
        r = await client.post(f"/rooms/{room_id}/bots", headers=_auth(token))
        assert r.status_code == 200, r.text
    await client.post(f"/rooms/{room_id}/start", headers=_auth(token))

    await client.post(f"/rooms/{room_id}/leave", headers=_auth(token))
    pub = (await client.get(f"/rooms/{room_id}", headers=_auth(token))).json()
    assert pub["match_over"] is True


@pytest.mark.asyncio
async def test_new_room_private_is_tagged_with_new_room(client, published):
    """Сценарий бага: игрок ушёл из матча и сел в новую комнату.

    Личный канал у него тот же, поэтому важно, что приватка новой комнаты помечена
    её room_id, а старая комната в этот канал больше не пишет.
    """
    ctx = await _make_room(client, 3)
    room_a, tokens, user_ids = ctx["room_id"], ctx["tokens"], ctx["user_ids"]
    await client.post(f"/rooms/{room_a}/start", headers=_auth(tokens[0]))
    await client.post(f"/rooms/{room_a}/leave", headers=_auth(tokens[1]))

    # Тот же игрок собирает новый стол с ботами и стартует.
    room_b = (
        await client.post("/rooms", json={"rules_code": E2E_RULES_CODE}, headers=_auth(tokens[1]))
    ).json()["room_id"]
    for _ in range(2):
        await client.post(f"/rooms/{room_b}/bots", headers=_auth(tokens[1]))

    published.clear()
    await client.post(f"/rooms/{room_b}/start", headers=_auth(tokens[1]))

    privates = _privates_for(published, user_ids[1])
    assert privates, "игрок не получил руку в новой комнате"
    assert all(p["room_id"] == room_b for p in privates)

    # Действие в старой комнате в его канал уже не попадает.
    published.clear()
    pub_a = (await client.get(f"/rooms/{room_a}", headers=_auth(tokens[0]))).json()
    seat_token = {s["seat"]: tokens[user_ids.index(s["user_id"])] for s in pub_a["seats"]}
    turn_seat = pub_a["turn"]["seat"]
    if turn_seat is not None and turn_seat in seat_token:
        hand = (await client.get(f"/rooms/{room_a}/hand", headers=_auth(seat_token[turn_seat]))).json()
        av = hand["available_actions"]
        body = (
            {"action_type": "bid", "payload": {"bid": av["options"][0]}}
            if av["type"] == "bid"
            else {"action_type": "play_card", "payload": {"card": av["cards"][0]}}
        )
        await client.post(f"/rooms/{room_a}/action", json=body, headers=_auth(seat_token[turn_seat]))
        assert _privates_for(published, user_ids[1]) == [], "старая комната пишет в личный канал"
