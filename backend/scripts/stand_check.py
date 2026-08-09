"""Сквозная проверка realtime на стенде через публичный путь.

Только публичные HTTPS/WSS-эндпоинты (CF → nginx → app/centrifugo):
  1) dev-логин игрока, получение Centrifugo-токена;
  2) создание комнаты;
  3) подключение по WSS и подписка на канал комнаты;
  4) вход второго игрока (сервер публикует lobby) → ждём push у подписчика.

Запуск (из папки backend):
  python scripts/stand_check.py
Переменные: BASE, WS, ORIGIN, PREFIX.
"""
import asyncio
import json
import os

import httpx
import websockets

BASE = os.getenv("BASE", "https://odessky.win")
WS = os.getenv("WS", "wss://odessky.win/connection/websocket")
ORIGIN = os.getenv("ORIGIN", "https://odessky.win")
PREFIX = os.getenv("PREFIX", "prod")


async def _recv(ws, timeout=8.0):
    while True:
        m = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
        if m == {}:
            await ws.send("{}")
            continue
        return m


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=20) as h:
        t1 = (await h.post("/auth/dev", json={"username": "rt1"})).json()["token"]
        h1 = {"Authorization": f"Bearer {t1}"}
        cent = (await h.get("/auth/centrifugo-token", headers=h1)).json()["token"]
        room = (await h.post("/rooms", json={}, headers=h1)).json()
        rid, code = room["room_id"], room["join_code"]
        channel = f"{PREFIX}:room:{rid}"
        print("room:", rid, "channel:", channel)

        async with websockets.connect(WS, origin=ORIGIN) as ws:
            await ws.send(json.dumps({"id": 1, "connect": {"token": cent}}))
            c = await _recv(ws)
            if "error" in c:
                print("CONNECT ERROR:", c["error"])
                return 1
            print("connected:", c.get("connect", {}).get("client"))

            await ws.send(json.dumps({"id": 2, "subscribe": {"channel": channel}}))
            s = await _recv(ws)
            if "error" in s:
                print("SUBSCRIBE ERROR:", s["error"])
                return 1
            print("subscribed")

            # Триггерим публикацию: второй игрок входит в комнату.
            t2 = (await h.post("/auth/dev", json={"username": "rt2"})).json()["token"]
            await h.post("/rooms/join", json={"join_code": code}, headers={"Authorization": f"Bearer {t2}"})

            for _ in range(10):
                m = await _recv(ws)
                push = m.get("push")
                if push and push.get("channel") == channel:
                    data = push.get("pub", {}).get("data", {})
                    print("OK: received push type =", data.get("type"),
                          "| seats =", len(data.get("state", {}).get("seats", [])))
                    return 0
            print("FAIL: push not received")
            return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
