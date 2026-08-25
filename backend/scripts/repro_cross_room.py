"""Проверка изоляции личного канала между комнатами (баг «Загружаем стол…»).

Сценарий: игрок садится в комнату A, уходит из неё посреди матча и заходит
в комнату B. Личный канал `{prefix}:user#{id}` один на человека, поэтому
недоигранная A может продолжать слать в него свой приватный вид и перебивать
руку из B — фронт видит рассинхрон public/private и залипает на загрузке.

Комнаты различаем по номеру места: в A игрок садится вторым (seat 1), в B
создаёт её сам (seat 0). Приватка с чужим seat пришла из A.

Запуск (из папки backend):
  python scripts/repro_cross_room.py
Переменные: BASE, WS, ORIGIN, PREFIX, LISTEN_SEC.
"""
import asyncio
import json
import os
import sys
import time

import httpx
import websockets

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

BASE = os.getenv("BASE", "https://odessky.win")
WS = os.getenv("WS", "wss://odessky.win/connection/websocket")
ORIGIN = os.getenv("ORIGIN", "https://odessky.win")
PREFIX = os.getenv("PREFIX", "prod")
LISTEN_SEC = float(os.getenv("LISTEN_SEC", "20"))


async def _recv(ws, timeout=10.0):
    """Прочитать следующий кадр, отвечая на ping-и Centrifugo ({} -> {})."""
    while True:
        m = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
        if m == {}:
            await ws.send("{}")
            continue
        return m


class Player:
    def __init__(self, http: httpx.AsyncClient, name: str):
        self.http = http
        self.name = name
        self.token = ""
        self.user_id = ""

    async def login(self) -> "Player":
        r = (await self.http.post("/auth/dev", json={"username": self.name})).json()
        self.token = r["token"]
        self.user_id = r["user"]["id"]
        return self

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    async def centrifugo_token(self) -> str:
        r = await self.http.get("/auth/centrifugo-token", headers=self.headers)
        return r.json()["token"]

    async def create_room(self) -> dict:
        r = await self.http.post("/rooms", json={}, headers=self.headers)
        r.raise_for_status()
        return r.json()

    async def join_room(self, code: str) -> dict:
        r = await self.http.post("/rooms/join", json={"join_code": code}, headers=self.headers)
        r.raise_for_status()
        return r.json()

    async def add_bot(self, room_id: str) -> dict:
        r = await self.http.post(f"/rooms/{room_id}/bots", headers=self.headers)
        r.raise_for_status()
        return r.json()

    async def start(self, room_id: str) -> dict:
        r = await self.http.post(f"/rooms/{room_id}/start", headers=self.headers)
        r.raise_for_status()
        return r.json()

    async def leave(self, room_id: str) -> None:
        r = await self.http.post(f"/rooms/{room_id}/leave", headers=self.headers)
        r.raise_for_status()

    async def hand(self, room_id: str) -> dict:
        r = await self.http.get(f"/rooms/{room_id}/hand", headers=self.headers)
        r.raise_for_status()
        return r.json()

    async def public(self, room_id: str) -> dict:
        r = await self.http.get(f"/rooms/{room_id}", headers=self.headers)
        r.raise_for_status()
        return r.json()

    async def act(self, room_id: str, body: dict) -> None:
        r = await self.http.post(f"/rooms/{room_id}/action", json=body, headers=self.headers)
        r.raise_for_status()


async def build_room(host: Player, guest: Player) -> tuple[str, int]:
    """Комната host + guest + бот, матч запущен. Возвращает (room_id, seat гостя)."""
    room = await host.create_room()
    room_id = room["room_id"]
    await guest.join_room(room["join_code"])
    await host.add_bot(room_id)
    await host.start(room_id)
    seat = (await guest.hand(room_id))["seat"]
    return room_id, seat


async def nudge_room(room_id: str, players: list[Player], delay: float = 2.0) -> None:
    """Сходить за того, чей сейчас ход, чтобы комната родила публикацию.

    Нужно для контрольной половины проверки: мало убедиться, что чужая приватка
    не приходит — своя обязана приходить.
    """
    await asyncio.sleep(delay)
    by_seat = {}
    for pl in players:
        try:
            by_seat[(await pl.hand(room_id))["seat"]] = pl
        except Exception:  # noqa: BLE001
            continue
    pub = await players[0].public(room_id)
    seat = pub["turn"]["seat"]
    actor = by_seat.get(seat)
    if actor is None:
        print(f"  (ход за местом {seat} — не наш игрок, публикацию не триггерим)")
        return
    av = (await actor.hand(room_id))["available_actions"]
    if not av:
        return
    body = (
        {"action_type": "bid", "payload": {"bid": av["options"][0]}}
        if av["type"] == "bid"
        else {"action_type": "play_card", "payload": {"card": av["cards"][0]}}
    )
    await actor.act(room_id, body)
    print(f"  (сходили за место {seat} в текущей комнате)")


async def main() -> int:
    stamp = int(time.time())
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as http:
        p = await Player(http, f"cross_p_{stamp}").login()
        q = await Player(http, f"cross_q_{stamp}").login()
        print(f"players: P={p.user_id} Q={q.user_id}")

        # Комната A: хост Q, наш игрок P садится вторым.
        room_a, seat_a = await build_room(host=q, guest=p)
        print(f"room A={room_a}, P seat={seat_a}")

        # Оба уходят: все места помечены left, матч A доигрывает авто-ход.
        await p.leave(room_a)
        await q.leave(room_a)
        print("both left room A (auto-play keeps it running)")

        # Комната B: хост P, значит место 0 — гарантированно не как в A.
        room_b, _ = await build_room(host=p, guest=q)
        seat_b = (await p.hand(room_b))["seat"]
        print(f"room B={room_b}, P seat={seat_b}")

        if seat_a == seat_b:
            print("SKIP: места в A и B совпали, комнаты не различить — перезапусти")
            return 2

        ch_user = f"{PREFIX}:user#{p.user_id}"
        ch_room_b = f"{PREFIX}:room:{room_b}"
        cent = await p.centrifugo_token()

        async with websockets.connect(WS, origin=ORIGIN, max_size=None) as ws:
            await ws.send(json.dumps({"id": 1, "connect": {"token": cent}}))
            c = await _recv(ws)
            if "error" in c:
                print("CONNECT ERROR:", c["error"])
                return 1
            for i, ch in enumerate((ch_user, ch_room_b), start=2):
                await ws.send(json.dumps({"id": i, "subscribe": {"channel": ch}}))
                s = await _recv(ws)
                if "error" in s:
                    print(f"SUBSCRIBE ERROR ({ch}):", s["error"])
                    return 1
            print(f"listening {LISTEN_SEC:.0f}s on {ch_user} + room B channel")
            nudge = asyncio.create_task(nudge_room(room_b, [p, q]))

            from_b = from_a = 0
            desync = 0
            public_b = (None, None)  # (round_index, phase) последнего публичного вида B
            deadline = time.monotonic() + LISTEN_SEC

            while time.monotonic() < deadline:
                try:
                    m = await _recv(ws, timeout=max(1.0, deadline - time.monotonic()))
                except asyncio.TimeoutError:
                    break
                push = m.get("push") or {}
                data = (push.get("pub") or {}).get("data") or {}
                channel = push.get("channel")

                if channel == ch_room_b and data.get("type") in ("state", "lobby"):
                    st = data.get("state") or {}
                    public_b = (st.get("round_index"), (st.get("round") or {}).get("phase"))
                elif channel == ch_user and data.get("type") == "private":
                    priv = data.get("private") or {}
                    # Если бэк уже помечает приватку комнатой — верим ей; на старом
                    # бэке (без room_id) отличаем по месту, оно в A и B разное.
                    alien = (
                        priv["room_id"] != room_b
                        if priv.get("room_id")
                        else priv.get("seat") != seat_b
                    )
                    if alien:
                        from_a += 1
                    else:
                        from_b += 1
                    # Ровно эта проверка живёт во фронте (isMeFresh в screen-resolver.ts):
                    # не сошлось — игрок видит «Загружаем стол…».
                    if (priv.get("round_index"), priv.get("phase")) != public_b:
                        desync += 1
                    print(
                        f"  private seat={priv.get('seat')} "
                        f"round={priv.get('round_index')} phase={priv.get('phase')} "
                        f"room_id={'—' if not priv.get('room_id') else priv['room_id'][:8]} "
                        f"{'<- ROOM A (alien)' if alien else '<- room B'}"
                    )

            await nudge

            print(f"\nprivate from room B: {from_b}")
            print(f"private from room A: {from_a}")
            print(f"public/private desync (экран загрузки): {desync}")
            if from_a:
                print("\nFAIL: приватка из покинутой комнаты течёт в личный канал")
                return 1
            if not from_b:
                print("\nFAIL: своя приватка тоже не доходит — проверка не показательна")
                return 1
            print("\nOK: личный канал отдаёт только текущую комнату")
            return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
