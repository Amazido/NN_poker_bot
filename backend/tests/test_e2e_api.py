"""E2E-тесты API: сквозной сценарий комнаты и полного матча.

Прогоняется через httpx ASGITransport поверх реального Postgres; live-стейт
in-memory, Centrifugo-паблиш no-op (см. conftest).
"""
import pytest

from app.core.centrifugo import ch_room, ch_user
from tests.conftest import E2E_RULES_CODE


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, name: str):
    r = await client.post("/auth/dev", json={"username": name})
    assert r.status_code == 200, r.text
    d = r.json()
    return d["token"], d["user"]["id"]


async def _make_room(client, n_players: int = 3):
    """Логин n игроков, создание комнаты и посадка всех. Возвращает контекст."""
    players = [await _login(client, f"E2E_{i}") for i in range(n_players)]
    tokens = [t for t, _ in players]
    user_ids = [uid for _, uid in players]

    r = await client.post("/rooms", json={"rules_code": E2E_RULES_CODE}, headers=_auth(tokens[0]))
    assert r.status_code == 200, r.text
    st = r.json()
    room_id, join_code = st["room_id"], st["join_code"]

    for t in tokens[1:]:
        rj = await client.post("/rooms/join", json={"join_code": join_code}, headers=_auth(t))
        assert rj.status_code == 200, rj.text

    return {"room_id": room_id, "join_code": join_code, "tokens": tokens, "user_ids": user_ids}


@pytest.mark.asyncio
async def test_health_and_dev_login(client):
    assert (await client.get("/health")).json()["status"] == "ok"
    token, uid = await _login(client, "solo")
    me = await client.get("/auth/me", headers=_auth(token))
    assert me.status_code == 200
    assert me.json()["user_type"] == "dev"


@pytest.mark.asyncio
async def test_lobby_create_join_start(client):
    ctx = await _make_room(client, 3)
    room_id, tokens = ctx["room_id"], ctx["tokens"]

    # Лобби: 3 игрока за столом.
    pub = (await client.get(f"/rooms/{room_id}", headers=_auth(tokens[0]))).json()
    assert pub["status"] == "lobby"
    assert pub["n_players"] == 3

    # Не создатель не может стартовать.
    bad = await client.post(f"/rooms/{room_id}/start", headers=_auth(tokens[1]))
    assert bad.status_code == 409

    # Старт создателем → матч играется, роздана первая раздача.
    started = await client.post(f"/rooms/{room_id}/start", headers=_auth(tokens[0]))
    assert started.status_code == 200, started.text
    s = started.json()
    assert s["status"] == "playing"
    assert s["round"] is not None
    assert s["turn"]["kind"] == "bid"


@pytest.mark.asyncio
async def test_full_match_flow(client):
    ctx = await _make_room(client, 3)
    room_id, tokens, user_ids = ctx["room_id"], ctx["tokens"], ctx["user_ids"]

    started = await client.post(f"/rooms/{room_id}/start", headers=_auth(tokens[0]))
    assert started.status_code == 200, started.text

    # seat -> token по user_id из публичного стейта.
    seats = started.json()["seats"]
    uid_to_token = {uid: tokens[i] for i, uid in enumerate(user_ids)}
    seat_token = {s["seat"]: uid_to_token[s["user_id"]] for s in seats}

    pub = started.json()
    for _ in range(2000):
        pub = (await client.get(f"/rooms/{room_id}", headers=_auth(tokens[0]))).json()
        if pub.get("match_over"):
            break

        turn = pub["turn"]
        kind, seat = turn["kind"], turn["seat"]
        assert kind in ("bid", "play"), f"unexpected turn: {turn}"
        token = seat_token[seat]

        hand = (await client.get(f"/rooms/{room_id}/hand", headers=_auth(token))).json()
        av = hand["available_actions"]
        assert av is not None and av["type"] == kind, f"hand/turn mismatch: {av} vs {kind}"

        if kind == "bid":
            body = {"action_type": "bid", "payload": {"bid": av["options"][0]}}
        else:
            assert av["cards"], "нет легальных карт на ходу розыгрыша"
            body = {"action_type": "play_card", "payload": {"card": av["cards"][0]}}

        act = await client.post(f"/rooms/{room_id}/action", json=body, headers=_auth(token))
        assert act.status_code == 200, act.text

    assert pub.get("match_over") is True, "матч не завершился за отведённые шаги"

    # Итог: все раздачи сыграны (round_index дошёл до конца), у всех есть счёт.
    assert pub["round_index"] >= pub["rounds_total"] - 1
    assert len(pub["seats"]) == 3
    for s in pub["seats"]:
        assert isinstance(s["score"], int)


@pytest.mark.asyncio
async def test_realtime_publishes_on_transitions(client, monkeypatch):
    """Сервер рассылает события в каналы Centrifugo на join/start/action."""
    records: list = []

    async def _rec(channel, data):
        records.append((channel, data))

    monkeypatch.setattr("app.poker.channels.safe_publish", _rec)

    ctx = await _make_room(client, 3)
    room_id, tokens, user_ids = ctx["room_id"], ctx["tokens"], ctx["user_ids"]

    # На create/join ушли снапшоты лобби в канал комнаты.
    assert any(c == ch_room(room_id) and d.get("type") == "lobby" for c, d in records)

    # Старт → публичный снапшот в канал комнаты + приватные руки каждому.
    records.clear()
    started = await client.post(f"/rooms/{room_id}/start", headers=_auth(tokens[0]))
    assert started.status_code == 200, started.text
    assert any(c == ch_room(room_id) and d.get("type") == "state" for c, d in records)
    for uid in user_ids:
        assert any(c == ch_user(uid) and d.get("type") == "private" for c, d in records)

    # Действие → снапшот (и, возможно, события) в канал комнаты.
    seats = started.json()["seats"]
    turn_seat = started.json()["turn"]["seat"]
    uid_to_token = {uid: tokens[i] for i, uid in enumerate(user_ids)}
    seat_token = {s["seat"]: uid_to_token[s["user_id"]] for s in seats}

    records.clear()
    hand = (await client.get(f"/rooms/{room_id}/hand", headers=_auth(seat_token[turn_seat]))).json()
    bid = hand["available_actions"]["options"][0]
    act = await client.post(
        f"/rooms/{room_id}/action",
        json={"action_type": "bid", "payload": {"bid": bid}},
        headers=_auth(seat_token[turn_seat]),
    )
    assert act.status_code == 200, act.text
    assert any(c == ch_room(room_id) and d.get("type") == "state" for c, d in records)


@pytest.mark.asyncio
async def test_action_rejected_when_not_your_turn(client):
    ctx = await _make_room(client, 3)
    room_id, tokens, user_ids = ctx["room_id"], ctx["tokens"], ctx["user_ids"]

    started = await client.post(f"/rooms/{room_id}/start", headers=_auth(tokens[0]))
    seats = started.json()["seats"]
    turn_seat = started.json()["turn"]["seat"]

    uid_to_token = {uid: tokens[i] for i, uid in enumerate(user_ids)}
    seat_token = {s["seat"]: uid_to_token[s["user_id"]] for s in seats}

    # Игрок не на ходу пытается сделать заказ → отказ (409).
    other_seat = next(s["seat"] for s in seats if s["seat"] != turn_seat)
    r = await client.post(
        f"/rooms/{room_id}/action",
        json={"action_type": "bid", "payload": {"bid": 0}},
        headers=_auth(seat_token[other_seat]),
    )
    assert r.status_code == 409, r.text
