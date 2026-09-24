"""Живая проверка формы правил: заготовки, свой стол, отказ по негодным правилам.

Зависит от DEBUG=true на стенде (логин через POST /auth/dev).

    python backend/scripts/table_rules_stand_check.py [https://odessky.win]
"""
import sys
import uuid

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://odessky.win"

FORM = {
    "rounds_start": 2,
    "rounds_peak": 4,
    "two_beats_ace": True,
    "offcolor_beats_oncolor": False,
    "blind_allowed": True,
    "blind_bonus": 7,
    "infinite_deck": False,
    "pass_reward": 15,
    "trick_reward": 20,
    "overtrick_penalty": 3,
    "undertrick_penalty": 8,
}


def check(cond, msg):
    print(("  OK  " if cond else " FAIL ") + msg)
    return bool(cond)


def main() -> int:
    tag = uuid.uuid4().hex[:6]
    ok = True
    with httpx.Client(base_url=BASE, timeout=20) as c:
        presets = c.get("/rules/presets").json()
        ok &= check(presets["season"], "эталон сезона отдаётся")
        ok &= check(
            presets["limits"]["max_peak_one_deck"] < presets["limits"]["max_peak_infinite"],
            "безлимитная колода поднимает потолок раздачи",
        )
        codes = {p["code"] for p in presets["presets"]}
        ok &= check("odessa_blitz" not in codes, "невыразимые формой редакции в заготовки не попали")

        r = c.post("/auth/dev", json={"username": f"form_{tag}"})
        r.raise_for_status()
        head = {"Authorization": f"Bearer {r.json()['token']}"}

        room = c.post("/rooms", json={"rules": FORM}, headers=head)
        ok &= check(room.status_code == 200, f"стол по своим правилам создан ({room.status_code})")
        if room.status_code == 200:
            rules = room.json()["rules"]
            ok &= check(rules["code"] == "custom", "стол подписан как «Свои правила»")
            ok &= check(rules["blind_bonus"] == 7, "надбавка за слепой заказ доехала")
            joined = " | ".join(rules["summary"])
            ok &= check("от 2 до 4 карт" in joined, f"раздачи из формы: {joined}")
            ok &= check("-3 за перебор" in joined, "штраф введён плюсом, записан минусом")
            c.post(f"/rooms/{room.json()['room_id']}/leave", headers=head)

        bad = c.post("/rooms", json={"rules": {**FORM, "rounds_peak": 13}}, headers=head)
        ok &= check(bad.status_code == 409, f"невлезающая раздача отбита ({bad.status_code})")

        big = c.post("/rooms", json={"rules": {**FORM, "rounds_peak": 13, "infinite_deck": True}}, headers=head)
        ok &= check(big.status_code == 200, "та же раздача на безлимитной колоде разрешена")
        if big.status_code == 200:
            c.post(f"/rooms/{big.json()['room_id']}/leave", headers=head)

        season = c.post("/rooms", json={"rules_code": presets["season"]["code"]}, headers=head)
        ok &= check(season.status_code == 200, "стол по правилам сезона создан")
        if season.status_code == 200:
            ok &= check(
                season.json()["rules"]["code"] == presets["season"]["code"],
                "сезонный стол помечен редакцией, а не «своими правилами»",
            )
            c.post(f"/rooms/{season.json()['room_id']}/leave", headers=head)

    print("ИТОГ:", "всё хорошо" if ok else "есть провалы")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
