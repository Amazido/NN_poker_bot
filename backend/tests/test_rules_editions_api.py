"""E2E по редакциям правил: каталог, выбор редакции столом, снапшот в матче."""
import pytest
from sqlalchemy import update

from app.db.models import RulesEditionModel
from tests.conftest import E2E_RULES_CODE
from tests.test_e2e_api import _auth, _login, _make_room


async def _seed_edition(client, *, code: str, config: dict, name: str = "Тестовая"):
    async with client.test_sessionmaker() as session:
        session.add(
            RulesEditionModel(
                code=code, version=1, name=name, config=config,
                meta={"description": f"описание {code}"}, is_active=True,
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_editions_endpoint_lists_active_editions(client):
    await _seed_edition(
        client,
        code="circular_test",
        config={"ranking": {"two_beats_ace_same_suit": True, "offcolor_beats_oncolor": True}},
    )
    r = await client.get("/rules/editions")
    assert r.status_code == 200, r.text

    by_code = {e["code"]: e for e in r.json()}
    assert E2E_RULES_CODE in by_code

    circular = by_code["circular_test"]
    assert circular["description"] == "описание circular_test"
    assert circular["min_players"] == 3 and circular["max_players"] == 5
    assert circular["rounds_total_hint"] > 0
    assert any("Двойка бьёт туза" in line for line in circular["summary"])


@pytest.mark.asyncio
async def test_public_view_carries_table_rules(client):
    """Игрок должен видеть, по каким правилам сел, — и в лобби, и в матче."""
    ctx = await _make_room(client, n_players=3)
    lobby = (await client.get(f"/rooms/{ctx['room_id']}", headers=_auth(ctx["tokens"][0]))).json()
    assert lobby["rules"]["code"] == E2E_RULES_CODE
    assert lobby["rules"]["summary"]

    await client.post(f"/rooms/{ctx['room_id']}/start", headers=_auth(ctx["tokens"][0]))
    playing = (await client.get(f"/rooms/{ctx['room_id']}", headers=_auth(ctx["tokens"][0]))).json()
    assert playing["rules"]["code"] == E2E_RULES_CODE
    assert playing["rules"]["summary"]


@pytest.mark.asyncio
async def test_unknown_rules_code_rejected(client):
    token, _ = await _login(client, "no_such_rules")
    r = await client.post("/rooms", json={"rules_code": "нет-такой"}, headers=_auth(token))
    assert r.status_code == 409, r.text


@pytest.mark.asyncio
async def test_unplayable_edition_rejected_at_room_creation(client):
    """Пятеро по 13 карт в колоду не влезают — ловим до стола, а не в середине матча."""
    await _seed_edition(
        client,
        code="too_deep",
        config={"rounds": {"peak": 13}, "players": {"min": 3, "max": 5}},
    )
    token, _ = await _login(client, "deep_host")
    r = await client.post("/rooms", json={"rules_code": "too_deep"}, headers=_auth(token))
    assert r.status_code == 409, r.text
    assert "не влезает" in r.json()["detail"]


@pytest.mark.asyncio
async def test_running_match_keeps_its_rules_snapshot(client):
    """Правка редакции не должна менять правила уже идущего матча.

    Без этой развязки нельзя ни выпускать новые версии правил, ни вести сезон.
    """
    ctx = await _make_room(client, n_players=3)
    await client.post(f"/rooms/{ctx['room_id']}/start", headers=_auth(ctx["tokens"][0]))

    before = (await client.get(f"/rooms/{ctx['room_id']}", headers=_auth(ctx["tokens"][0]))).json()
    rounds_total_before = before["rounds_total"]

    async with client.test_sessionmaker() as session:
        await session.execute(
            update(RulesEditionModel)
            .where(RulesEditionModel.code == E2E_RULES_CODE)
            .values(config={"rounds": {"mode": "custom", "sequence": [1]},
                            "scoring": {"exact_per_trick": 999}})
        )
        await session.commit()

    after = (await client.get(f"/rooms/{ctx['room_id']}", headers=_auth(ctx["tokens"][0]))).json()
    assert after["rounds_total"] == rounds_total_before
    assert any("+10" in line for line in after["rules"]["summary"])
