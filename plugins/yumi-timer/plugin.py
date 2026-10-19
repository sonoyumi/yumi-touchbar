#!/usr/bin/env python3
"""Плагин touchbard «yumi-timer» (тачбар yumi, 19.10.2026): быстрые таймеры 5 / 15 / 25 / 50 минут.

Касание по ячейке — таймер сразу пошёл; отсчёт и конец показывает полоса yumi-pomodoro (общий файл
yumi_pomo_state). Идущий таймер того же размера подсвечен акцентом.
Опции: { plugin = "yumi-timer", width = 360, options = { minutes = [5, 15, 25, 50] } }
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from yumi_glow_lib import Host
from yumi_cells import Pal, cell, row
import yumi_pomo_state as P

tap = {}


def mins(opts):
    return [int(m) for m in (opts.get("minutes") or [5, 15, 25, 50])][:6]


def on_tap(host, x):
    w = (host.size or (0, 0))[0]
    ms = mins(host.opts)
    i = min(len(ms) - 1, int(x / (w / len(ms))))
    tap[i] = time.monotonic(); host.animate(0.35)
    P.save(P.timer(ms[i]))


def draw(host, c, w, h, theme, opts, now):
    pal, k = Pal(theme), host.intro()
    d = P.load()
    ms = mins(opts)
    cw = w / len(ms)
    for i, m in enumerate(ms):
        on = d["mode"] == "timer" and P.running(d) and d["total"] == m * 60
        cell(c, i * cw, cw, h, pal, k, tap.get(i, -9), now, fill=pal.accent if on else None)
        ink = pal.surface if on else pal.fg
        row(c, pal, [(str(m), 19, ink, True, False), ("мин", 13, pal.surface if on else pal.dim, False, False)], i * cw, cw, h, k, gap=5)


Host(on_tap).run(draw)              # подсветку обновляет кадр-«пульс» Host раз в 1 с
