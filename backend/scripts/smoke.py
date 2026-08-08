"""Сквозной smoke-тест через ASGI: dev-логин, комната, старт, авто-розыгрыш.

Запуск (нужны запущенные Postgres/Redis):
  python -m scripts.smoke
"""
import asyncio

import httpx

from app.main import app


async def run() -> None:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            tokens = {}   # user_id -> token
            for name in ("Alice", "Bob", "Carol"):
                r = await c.post("/auth/dev", json={"username": name})
                r.raise_for_status()
                d = r.json()
                tokens[d["user"]["id"]] = d["token"]
            uids = list(tokens.keys())
            hdr = lambda uid: {"Authorization": f"Bearer {tokens[uid]}"}

            # Создать комнату (Alice) и войти остальным.
            r = await c.post("/rooms", json={}, headers=hdr(uids[0]))
            r.raise_for_status()
            room = r.json()
            room_id = room["room_id"]
            join_code = room["join_code"]
            print("room:", room_id, "code:", join_code)

            for uid in uids[1:]:
                r = await c.post("/rooms/join", json={"join_code": join_code}, headers=hdr(uid))
                r.raise_for_status()

            # Старт матча.
            r = await c.post(f"/rooms/{room_id}/start", headers=hdr(uids[0]))
            r.raise_for_status()
            state = r.json()
            print("started. round_index=", state["round_index"], "cards=", state["round"]["cards_count"])

            # Играем, пока не дойдём до раунда 3 (3 полных раздачи) или конца матча.
            steps = 0
            while not state["match_over"] and state["round_index"] < 3 and steps < 500:
                steps += 1
                turn = state["turn"]
                seat = turn["seat"]
                uid = next(s["user_id"] for s in state["seats"] if s["seat"] == seat)

                h = (await c.get(f"/rooms/{room_id}/hand", headers=hdr(uid))).json()
                act = h["available_actions"]
                if act is None:
                    # На всякий случай — обновим публичное состояние.
                    state = (await c.get(f"/rooms/{room_id}", headers=hdr(uid))).json()
                    continue

                if act["type"] == "bid":
                    payload = {"action_type": "bid", "payload": {"bid": act["options"][0]}}
                else:
                    payload = {"action_type": "play_card", "payload": {"card": act["cards"][0]}}

                r = await c.post(f"/rooms/{room_id}/action", json=payload, headers=hdr(uid))
                r.raise_for_status()
                state = r.json()

            scores = {s["seat"]: s["score"] for s in state["seats"]}
            print(f"OK after {steps} actions. round_index={state['round_index']} "
                  f"match_over={state['match_over']} scores={scores}")


if __name__ == "__main__":
    asyncio.run(run())
