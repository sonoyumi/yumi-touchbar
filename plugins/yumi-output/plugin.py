#!/usr/bin/env python3
"""Плагин touchbard «yumi-output» (тачбар yumi, 19.10.2026): выход звука — текущий и «следующий по кругу».

Подпись — понятное имя выхода: AirPods (имя из Bluetooth), «MacBook» со значком ноутбука (j293-convolver —
DSP Asahi), «Колонки» со значком колонки (HiFi Headphones — разъём 3,5 мм). Касание — следующий выход: pactl set-default-sink (PipeWire сам переносит
звучащие потоки). Скрытые и «сырые» выходы динамиков (без DSP) в круг не входят — громко и без защиты.
Поведение службы yumi-airpods не меняется: она по-прежнему сама делает AirPods выходом при подключении
и возвращает прошлый выход, когда наушники в кейсе; кнопка — только ручной выбор.
Данные — pactl раз в 2 с (и сразу после касания).
Опции: { plugin = "yumi-output", width = 230 }
"""
import json, os, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from yumi_glow_lib import Host
from yumi_cells import Pal, cell, glyph, text, fit, run

G = {"bt": "\U000F02CB", "mac": "\U000F0322", "spk": "\U000F04C3"}   # наушники BT, ноутбук (MacBook), колонка (3,5 мм)
tap_at = [-9.0]
state = {"sinks": [], "cur": ""}
wake = threading.Event()


def nice(s):
    name, desc = s.get("name", ""), s.get("description") or ""
    props = s.get("properties") or {}
    if name.startswith("bluez_output"):
        return "bt", props.get("device.alias") or desc or "Bluetooth"
    if "convolver" in name or "Speakers" in desc:
        return "mac", "MacBook"                       # встроенные динамики
    if "Headphones" in name or "Headphones" in desc:
        return "spk", "Колонки"                       # разъём 3,5 мм — там колонки
    return "spk", desc or name


def usable(s):
    name = s.get("name", "")
    props = s.get("properties") or {}
    if props.get("node.hidden") in (True, "true", "1"):
        return False
    if "Speaker" in name and name.startswith("alsa_output"):   # сырые динамики без DSP
        return False
    return True


def read():
    try:
        sinks = json.loads(run("pactl", "-f", "json", "list", "sinks") or "[]")
    except ValueError:
        sinks = []
    state["sinks"] = [s for s in sinks if usable(s)]
    state["cur"] = run("pactl", "get-default-sink").strip()


def poller(host):
    last = None
    while True:
        read()
        cur = (state["cur"], tuple(s.get("name") for s in state["sinks"]))
        if cur != last:
            last = cur
            with host.lock:
                host.dirty = True
        wake.wait(2.0); wake.clear()


started = [False]


def tick(host, now):
    if not started[0] and host.size:
        started[0] = True
        threading.Thread(target=poller, args=(host,), daemon=True).start()


def on_tap(host, x):
    tap_at[0] = time.monotonic(); host.animate(0.35)
    names = [s.get("name") for s in state["sinks"]]
    if not names:
        return
    i = names.index(state["cur"]) if state["cur"] in names else -1
    nxt = names[(i + 1) % len(names)]
    run("pactl", "set-default-sink", nxt)
    state["cur"] = nxt
    wake.set()


def draw(host, c, w, h, theme, opts, now):
    pal, k = Pal(theme), host.intro()
    cell(c, 0, w, h, pal, k, tap_at[0], now)
    cur = next((s for s in state["sinks"] if s.get("name") == state["cur"]), None)
    kind, label = nice(cur) if cur else ("spk", "…")
    x = 16
    x += glyph(c, pal, G[kind], 26, x, h, pal.accent, k) + 12
    n = len(state["sinks"])
    hint = f"1/{n}" if n < 2 else f"{[s.get('name') for s in state['sinks']].index(state['cur']) + 1 if cur else '?'}/{n}"
    text(c, pal, fit(c, pal, label, 17, w - x - 52), 17, x, h, pal.fg, k)
    text(c, pal, hint, 12, w - 44, h, pal.dim, k, bold=False)


Host(on_tap).run(draw, tick)
