#!/usr/bin/env python3
"""Плагин touchbard «yumi-ram» (тачбар yumi, 19.10.2026): сколько памяти занято из всей (на ноутбуке 8 ГБ).

Ячейка: значок, полоса занятого, «5,1 / 7,6 ГБ»; занято больше 85 % — полоса жёлтая, больше 93 % — красная.
Данные — /proc/meminfo раз в 2 с (занято = MemTotal − MemAvailable), под полосой мелко — своп/zram, если занят.
Касание — yumi-sysmon (btop); своя команда — options.command.
Опции: { plugin = "yumi-ram", width = 300 }
"""
import os, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from yumi_glow_lib import Host, mix, rounded
from yumi_cells import Pal, cell, glyph, text, text_w, spawn

GLYPH = "\U000F035B"           # memory
tap_at = [-9.0]
mem = {"used": None, "total": None, "swap": 0.0}


def read():
    info = {}
    try:
        for line in open("/proc/meminfo"):
            k, v = line.split(":", 1)
            info[k] = int(v.split()[0]) * 1024
    except (OSError, ValueError):
        return
    total, avail = info.get("MemTotal"), info.get("MemAvailable")
    if total and avail is not None:
        mem.update(used=total - avail, total=total, swap=max(0, info.get("SwapTotal", 0) - info.get("SwapFree", 0)))


def gb(b):
    return f"{b / 2**30:.1f}".replace(".", ",")


def poller(host):
    last = None
    while True:
        read()
        cur = (round((mem["used"] or 0) / 2**24), round(mem["swap"] / 2**24))
        if cur != last:
            last = cur
            with host.lock:
                host.dirty = True
        time.sleep(2.0)


started = [False]


def tick(host, now):
    if not started[0] and host.size:
        started[0] = True
        threading.Thread(target=poller, args=(host,), daemon=True).start()


def on_tap(host, x):
    tap_at[0] = time.monotonic(); host.animate(0.35)
    spawn(host.opts.get("command") or "yumi-sysmon")


def draw(host, c, w, h, theme, opts, now):
    pal, k = Pal(theme), host.intro()
    cell(c, 0, w, h, pal, k, tap_at[0], now)
    used, total = mem["used"], mem["total"]
    frac = used / total if used and total else 0.0
    ink = pal.red if frac > .93 else (pal.yellow if frac > .85 else pal.accent)
    x = 18
    x += glyph(c, pal, GLYPH, 28, x, h, ink, k) + 12
    label = f"{gb(used)} / {gb(total)} ГБ" if used else "…"
    lw = text_w(c, pal, label, 17)
    bar_w = max(40, w - x - lw - 32)
    by = h / 2 - 5
    rounded(c, x, by, bar_w, 10, 5); c.set_source_rgba(*mix(pal.surface, pal.fg, .12), k); c.fill()
    if frac:
        rounded(c, x, by, max(10, bar_w * frac), 10, 5); c.set_source_rgba(*ink, k); c.fill()
    if mem["swap"] > 2**26:
        text(c, pal, f"своп {gb(mem['swap'])}", 11, x, h, pal.dim, k, bold=False, cy=h / 2 + 14)
    text(c, pal, label, 17, x + bar_w + 14, h, pal.fg, k)


Host(on_tap).run(draw, tick)
