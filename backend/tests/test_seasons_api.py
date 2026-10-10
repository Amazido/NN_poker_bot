"""E2E-тесты сезона: запись итогов матчей, зачётность и рейтинг.

Проверяем именно то, ради чего всё это собрано: матч попал в метрики один раз,
правильно размечен (зачётный / нет и почему), а рейтинг изменился ровно на
записанную в журнал дельту.
"""
import pytest

from tests.conftest import E2E_RULES_CODE
from tests.test_e2e_api import _auth, _make_room


async def _seed_season(client, *, rules_code: str = E2E_RULES_CODE, initial_rating: int = 1000):
    """Открыть сезон на указанной редакции правил.

    Сезон привязан к редакции: матч идёт в зачёт только за столом с правилами
    сезона. Поэтому для «домашних правил» достаточно открыть сезон на другой.
    """
    from app.repositories.pg import RulesEditionRepository, SeasonRepository

    async with client.test_sessionmaker() as session:
        edition = await RulesEditionRepository(session).get_active_by_code(rules_code)
        assert edition is not None, f"нет редакции {rules_code}"
        return await SeasonRepository(session).create_season(
            code="test_season",
            name="Тестовый сезон",
            rules_edition_id=edition.id,
            initial_rating=initial_rating,
        )


async def _other_edition(client):
    """Завести вторую редакцию правил — чтобы сезон смотрел не на стол e2e."""
    from app.repositories.pg import RulesEditionRepository

    async with client.test_sessionmaker() as session:
        await RulesEditionRepository(session).create(
            code="e2e_other",
            version=1,
            name="Другая редакция",
            config={"rounds": {"mode": "custom", "sequence": [1]}, "players": {"min": 3, "max": 5}},
            meta={"author": "e2e"},
            is_active=True,
        )
    return "e2e_other"


async def _bot_move(client, room_id: str) -> None:
    """Сделать ход за бота так же, как это делает фоновый таймер.

    В тестах таймер не запущен, поэтому дёргаем ту же пару
    `choose_auto_action` + `PokerService.act` напрямую.
    """
    from app.poker import state as state_store
    from app.poker.autoplay import choose_auto_action
    from app.poker.service import PokerService
    from app.repositories.pg import (
        RoomRepository,
        RoundRepository,
        RulesEditionRepository,
        UserRepository,
    )

    state = await state_store.load_state(room_id)
    seat, action_type, payload = choose_auto_action(state)
    user_id = next(s["user_id"] for s in state["seats"] if s["seat"] == seat)
    async with client.test_sessionmaker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get(user_id)
        service = PokerService(
            session=session,
            user_repo=user_repo,
            rules_repo=RulesEditionRepository(session),
            room_repo=RoomRepository(session),
            round_repo=RoundRepository(session),
        )
        await service.act(user, room_id, action_type, payload)


async def _play_match_to_end(client, ctx) -> dict:
    """Доиграть матч до конца простейшей стратегией. Возвращает финальный стейт."""
    room_id, tokens, user_ids = ctx["room_id"], ctx["tokens"], ctx["user_ids"]
    started = await client.post(f"/rooms/{room_id}/start", headers=_auth(tokens[0]))
    assert started.status_code == 200, started.text

    uid_to_token = {uid: tokens[i] for i, uid in enumerate(user_ids)}
    seat_token = {
        s["seat"]: uid_to_token[s["user_id"]]
        for s in started.json()["seats"]
        if s["user_id"] in uid_to_token
    }

    pub = started.json()
    for _ in range(2000):
        pub = (await client.get(f"/rooms/{room_id}", headers=_auth(tokens[0]))).json()
        if pub.get("match_over"):
            return pub
        turn = pub["turn"]
        token = seat_token.get(turn["seat"])
        if not token:  # место бота
            await _bot_move(client, room_id)
            continue
        hand = (await client.get(f"/rooms/{room_id}/hand", headers=_auth(token))).json()
        av = hand["available_actions"]
        if turn["kind"] == "bid":
            body = {"action_type": "bid", "payload": {"bid": av["options"][0]}}
        else:
            body = {"action_type": "play_card", "payload": {"card": av["cards"][0]}}
        act = await client.post(f"/rooms/{room_id}/action", json=body, headers=_auth(token))
        assert act.status_code == 200, act.text
    raise AssertionError("матч не завершился за отведённые шаги")


@pytest.mark.asyncio
async def test_rated_match_recorded_once_with_rating(client):
    await _seed_season(client)
    ctx = await _make_room(client, 3)
    pub = await _play_match_to_end(client, ctx)
    tokens = ctx["tokens"]

    matches = (await client.get("/seasons/current/matches", headers=_auth(tokens[0]))).json()
    assert len(matches) == 1, matches
    m = matches[0]
    assert m["rated"] is True and m["unrated_reason"] is None
    assert m["outcome"] == "completed"
    assert m["n_players"] == 3
    assert m["rounds_played"] == m["rounds_total"] == pub["rounds_total"]

    # Места согласованы со счётом, дельты — по согласованной шкале для трёх
    # игроков (+1 / 0 / -1) и в сумме дают ноль.
    by_seat = {p["seat_index"]: p for p in m["players"]}
    final = {s["seat"]: s["score"] for s in pub["seats"]}
    for seat, p in by_seat.items():
        assert p["score"] == final[seat]
        assert p["is_bot"] is False and p["left_match"] is False
        assert p["rating_before"] == 1000
        assert p["rating_after"] == p["rating_before"] + p["rating_delta"]
    assert sum(p["rating_delta"] for p in m["players"]) <= 0, "ничья не печатает рейтинг"
    best = min(m["players"], key=lambda p: p["place"])
    assert best["score"] == max(final.values())
    assert best["rating_delta"] == max(p["rating_delta"] for p in m["players"])

    # Рейтинг в лидерборде = начальный + дельта, и в журнале есть событие матча.
    board = (await client.get("/seasons/current/leaderboard", headers=_auth(tokens[0]))).json()
    assert len(board) == 3
    assert [r["rating"] for r in board] == sorted((r["rating"] for r in board), reverse=True)
    mine = (await client.get("/seasons/current/me", headers=_auth(tokens[0]))).json()
    assert mine["matches"] == 1
    assert len(mine["events"]) == 1
    ev = mine["events"][0]
    assert ev["kind"] == "match"
    assert ev["rating_before"] == 1000 and ev["rating_after"] == 1000 + ev["delta"]
    assert mine["rating"] == ev["rating_after"]

    # Сводка по сезону видит матч ровно один раз.
    season = (await client.get("/seasons/current", headers=_auth(tokens[0]))).json()
    assert season["initial_rating"] == 1000
    assert season["matches_rated"] == 1
    assert season["matches_unrated"] == 0 and season["matches_abandoned"] == 0


@pytest.mark.asyncio
async def test_match_with_bot_is_unrated(client):
    """Бот за столом — матч не идёт в зачёт, но в метрики попадает."""
    await _seed_season(client)
    ctx = await _make_room(client, 3)
    room_id, tokens = ctx["room_id"], ctx["tokens"]
    r = await client.post(f"/rooms/{room_id}/bots", headers=_auth(tokens[0]))
    assert r.status_code == 200, r.text

    await _play_match_to_end(client, ctx)

    matches = (await client.get("/seasons/current/matches", headers=_auth(tokens[0]))).json()
    assert len(matches) == 1
    m = matches[0]
    assert m["rated"] is False and m["unrated_reason"] == "bots"
    assert m["n_players"] == 4
    assert sum(1 for p in m["players"] if p["is_bot"]) == 1
    # Рейтинг не начислен никому, но «с каким рейтингом садились» записано.
    assert all(p["rating_delta"] is None and p["rating_after"] is None for p in m["players"])
    assert any(p["rating_before"] == 1000 for p in m["players"] if not p["is_bot"])

    board = (await client.get("/seasons/current/leaderboard", headers=_auth(tokens[0]))).json()
    assert board == []
    mine = (await client.get("/seasons/current/me", headers=_auth(tokens[0]))).json()
    assert mine["rating"] == 1000 and mine["events"] == []


@pytest.mark.asyncio
async def test_house_rules_match_is_unrated(client):
    """Стол играет не по правилам сезона — матч не зачётный."""
    other = await _other_edition(client)
    await _seed_season(client, rules_code=other)
    ctx = await _make_room(client, 3)
    await _play_match_to_end(client, ctx)

    matches = (await client.get("/seasons/current/matches", headers=_auth(ctx["tokens"][0]))).json()
    assert len(matches) == 1
    assert matches[0]["rated"] is False
    assert matches[0]["unrated_reason"] == "house_rules"


@pytest.mark.asyncio
async def test_abandoned_match_keeps_current_scores(client):
    """Все вышли — матч всё равно записан, финальным стал счёт на момент выхода."""
    await _seed_season(client)
    ctx = await _make_room(client, 3)
    room_id, tokens = ctx["room_id"], ctx["tokens"]
    started = await client.post(f"/rooms/{room_id}/start", headers=_auth(tokens[0]))
    assert started.status_code == 200, started.text

    for t in tokens:
        r = await client.post(f"/rooms/{room_id}/leave", headers=_auth(t))
        assert r.status_code == 200, r.text

    pub = (await client.get(f"/rooms/{room_id}", headers=_auth(tokens[0]))).json()
    assert pub["match_over"] is True

    matches = (await client.get("/seasons/current/matches", headers=_auth(tokens[0]))).json()
    assert len(matches) == 1
    m = matches[0]
    assert m["outcome"] == "abandoned"
    assert m["rounds_played"] < m["rounds_total"]
    # Выход не отменяет результат: матч зачётный, дельты начислены.
    assert m["rated"] is True
    assert all(p["left_match"] is True for p in m["players"])
    assert all(p["rating_delta"] is not None for p in m["players"])
    final = {s["seat"]: s["score"] for s in pub["seats"]}
    assert {p["seat_index"]: p["score"] for p in m["players"]} == final

    season = (await client.get("/seasons/current", headers=_auth(tokens[0]))).json()
    assert season["matches_abandoned"] == 1


@pytest.mark.asyncio
async def test_without_season_match_is_recorded_but_not_rated(client):
    """Без сезона матч всё равно сохраняется — метрики собираются всегда."""
    ctx = await _make_room(client, 3)
    tokens = ctx["tokens"]
    await _play_match_to_end(client, ctx)

    assert (await client.get("/seasons/current", headers=_auth(tokens[0]))).status_code == 404
    all_matches = (
        await client.get("/seasons/current/matches?all_seasons=true", headers=_auth(tokens[0]))
    ).json()
    assert len(all_matches) == 1
    assert all_matches[0]["rated"] is False
    assert all_matches[0]["unrated_reason"] == "no_season"
    assert all(p["rating_before"] is None for p in all_matches[0]["players"])


@pytest.mark.asyncio
async def test_one_active_season_at_a_time(client):
    """Второй активный сезон не завести — иначе непонятно, в какой писать."""
    from sqlalchemy.exc import IntegrityError

    await _seed_season(client)
    with pytest.raises(IntegrityError):
        await _seed_season(client)
