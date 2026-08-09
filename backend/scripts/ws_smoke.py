"""Живой смоук realtime-обмена через Centrifugo.

Подключается к Centrifugo по WebSocket с JWT-токеном, подписывается на канал
комнаты, публикует туда сообщение через серверный HTTP API и проверяет, что
подписчик его получил. Используется для проверки транспорта и конфигурации
(namespace, allowed_origins, секреты) на dev и на стенде.

Запуск (dev, из папки backend):
  python scripts/ws_smoke.py

Против стенда (пример):
  WS_URL=wss://odessky.win/connection/websocket \
  CENTRIFUGO_API_URL=http://127.0.0.1:8001/api \
  CENTRIFUGO_API_KEY=... CENTRIFUGO_TOKEN_SECRET=... \
  CENTRIFUGO_CHANNEL_PREFIX=prod WS_ORIGIN=https://odessky.win \
  python scripts/ws_smoke.py
"""
import asyncio
import json
import os
import time

import jwt as pyjwt
import websockets
from cent import AsyncClient, PublishRequest

WS_URL = os.getenv("WS_URL", "ws://localhost:8001/connection/websocket")
WS_ORIGIN = os.getenv("WS_ORIGIN", "http://localhost:3000")
API_URL = os.getenv("CENTRIFUGO_API_URL", "http://localhost:8001/api")
API_KEY = os.getenv("CENTRIFUGO_API_KEY", "dev-centrifugo-api-key")
TOKEN_SECRET = os.getenv("CENTRIFUGO_TOKEN_SECRET", "dev-centrifugo-secret")
PREFIX = os.getenv("CENTRIFUGO_CHANNEL_PREFIX", "dev")
USER_ID = os.getenv("WS_USER", "smoke-user")


def _connect_token() -> str:
    now = int(time.time())
    return pyjwt.encode(
        {"sub": USER_ID, "iat": now, "exp": now + 300}, TOKEN_SECRET, algorithm="HS256"
    )


async def _recv(ws, timeout=5.0):
    """Прочитать кадр, автоматически отвечая на ping ({}) сервера."""
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        msg = json.loads(raw)
        if msg == {}:  # ping от сервера → отвечаем пустым кадром
            await ws.send("{}")
            continue
        return msg


async def main() -> int:
    channel = f"{PREFIX}:room:smoke"
    token = _connect_token()

    async with websockets.connect(WS_URL, origin=WS_ORIGIN) as ws:
        await ws.send(json.dumps({"id": 1, "connect": {"token": token}}))
        reply = await _recv(ws)
        if "error" in reply:
            print("CONNECT ERROR:", reply["error"])
            return 1
        print("connected:", reply.get("connect", {}).get("client"))

        await ws.send(json.dumps({"id": 2, "subscribe": {"channel": channel}}))
        reply = await _recv(ws)
        if "error" in reply:
            print("SUBSCRIBE ERROR:", reply["error"])
            return 1
        print("subscribed:", channel)

        payload = {"type": "smoke", "nonce": int(time.time())}
        client = AsyncClient(api_url=API_URL, api_key=API_KEY)
        try:
            await client.publish(PublishRequest(channel=channel, data=payload))
        finally:
            close = getattr(client, "close", None)
            if close is not None:
                res = close()
                if hasattr(res, "__await__"):
                    await res
        print("published:", payload)

        for _ in range(10):
            msg = await _recv(ws)
            push = msg.get("push")
            if push and push.get("channel") == channel:
                got = push.get("pub", {}).get("data")
                if got == payload:
                    print("OK: received push", got)
                    return 0
                print("push with unexpected data:", got)
        print("FAIL: push not received")
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
