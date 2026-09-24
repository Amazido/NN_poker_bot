"""Живая проверка «тёмной» на стенде: рука закрыта, открытие руки работает.

Зависит от DEBUG=true на стенде (логин через POST /auth/dev), как и остальные
скрипты в этой папке.

    python backend/scripts/blind_stand_check.py [https://odessky.win]
"""
import sys
import uuid

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://odessky.win"
CODE = "odessa_season_1"


def login(c, name):
    r = c.post("/auth/dev", json={"username": name})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def check(cond, msg):
    print(("  OK  " if cond else " FAIL ") + msg)
    return cond


def main() -> int:
    tag = uuid.uuid4().hex[:6]
    ok = True
    with httpx.Client(base_url=BASE, timeout=20) as c:
        host = login(c, f"blind_{tag}_0")

        r = c.post("/rooms", json={"rules_code": CODE}, headers=host)
        r.raise_for_status()
        room_id = r.json()["room_id"]
        print(f"room {room_id} on {CODE}")

        for _ in range(2):
            c.post(f"/rooms/{room_id}/bots", headers=host).raise_for_status()
        c.post(f"/rooms/{room_id}/start", headers=host).raise_for_status()

        pub = c.get(f"/rooms/{room_id}", headers=host).json()
        ok &= check(pub["rules"]["blind_bonus"] == 5, "правила стола отдают надбавку +5")

        hand = c.get(f"/rooms/{room_id}/hand", headers=host).json()
        ok &= check(hand["hand"] == [] and hand["hand_hidden"], "рука закрыта до открытия")
        ok &= check(hand["hand_count"] == 1, f"счётчик карт виден: {hand['hand_count']}")
        ok &= check(hand["can_open_hand"], "открыть руку можно")

        r = c.post(
            f"/rooms/{room_id}/action",
            json={"action_type": "open_hand", "payload": {}},
            headers=host,
        )
        ok &= check(r.status_code == 200, f"open_hand принят ({r.status_code})")

        hand = c.get(f"/rooms/{room_id}/hand", headers=host).json()
        ok &= check(len(hand["hand"]) == 1 and not hand["hand_hidden"], "рука открылась")

        c.post(f"/rooms/{room_id}/leave", headers=host)

    print("ИТОГ:", "всё хорошо" if ok else "есть провалы")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
