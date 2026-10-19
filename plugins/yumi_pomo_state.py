"""Общее состояние Pomodoro и таймеров тачбара yumi (19.10.2026): ~/.local/state/yumi-pomodoro.json.

Пишут yumi-pomodoro (старт/пауза/сброс/смена фазы) и yumi-timer (быстрые таймеры), читают оба.
Поля: mode focus|break|long|timer, total (с), left (с, пока на паузе), end (время конца, пока идёт), round (1…4).
Атомарная запись (tmp + rename) — читатель не увидит половину файла.
"""
import json, os, time

PATH = os.path.expanduser("~/.local/state/yumi-pomodoro.json")
FOCUS, BREAK, LONG, ROUNDS = 25 * 60, 5 * 60, 15 * 60, 4
DEFAULT = {"mode": "focus", "total": FOCUS, "left": FOCUS, "end": None, "round": 1}


def load():
    try:
        with open(PATH) as f:
            d = json.load(f)
        return {**DEFAULT, **d}
    except (OSError, ValueError):
        return dict(DEFAULT)


def save(d):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    tmp = PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(d, f)
    os.replace(tmp, PATH)


def left(d, now=None):
    """Сколько секунд осталось (идёт — по end, пауза — left)."""
    if d.get("end"):
        return max(0, int(round(d["end"] - (now or time.time()))))
    return int(d.get("left", d["total"]))


def running(d):
    return bool(d.get("end"))


def start(d):
    if not running(d):
        d["end"] = time.time() + left(d)
    return d


def pause(d):
    if running(d):
        d["left"], d["end"] = left(d), None
    return d


def reset(d):
    return dict(DEFAULT)


def timer(minutes):
    t = int(minutes) * 60
    return {"mode": "timer", "total": t, "left": t, "end": time.time() + t, "round": 1}


def next_phase(d):
    """Фаза кончилась: фокус → перерыв (каждый 4-й — длинный), перерыв → следующий круг фокуса; таймер → фокус."""
    if d["mode"] == "focus":
        long_ = d["round"] >= ROUNDS
        t = LONG if long_ else BREAK
        return {"mode": "long" if long_ else "break", "total": t, "left": t, "end": None, "round": d["round"]}
    rnd = 1 if d["mode"] in ("long", "timer") else d["round"] + 1
    return {"mode": "focus", "total": FOCUS, "left": FOCUS, "end": None, "round": rnd}
