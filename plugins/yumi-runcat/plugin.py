#!/usr/bin/env python3
"""Плагин touchbard «yumi-runcat» (тачбар yumi, 19.10.2026): кот бежит тем быстрее, чем выше загрузка CPU.

Кадры — кот из RunCat365 (frames/, Apache-2.0, см. frames/NOTICE): 5 кадров бега 120×100, форма = альфа,
глаза — прозрачные. Плагин заливает форму цветом: акцент бара (меняется с обоями), > 85 % — жёлтый, > 95 % — красный.
Загрузка — /proc/stat раз в 0,5 с, сглаженная; скорость 3 кадра/с в простое … 20 кадров/с при 100 %.
Касание — yumi-sysmon (btop); своя команда — options.command.
Опции: { plugin = "yumi-runcat", width = 104, options = { pct = false } }   pct — подпись «23%» справа от кота
"""
import os, sys, threading, time
import cairo
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from yumi_glow_lib import Host
from yumi_cells import Pal, cell, text, text_w, spawn

HERE = os.path.dirname(os.path.realpath(__file__))
FRAMES = [cairo.ImageSurface.create_from_png(os.path.join(HERE, "frames", f"cat_running_{i}.png")) for i in range(5)]


def bbox(frames):
    """Общая рамка непрозрачного по всем кадрам — чтобы кот не прыгал и не было пустых полей."""
    x0 = y0 = 10**9; x1 = y1 = -1
    for s in frames:
        s.flush()
        data, st = bytes(s.get_data()), s.get_stride()
        for y in range(s.get_height()):
            row = data[y * st:(y + 1) * st]
            xs = [x for x in range(s.get_width()) if row[4 * x + 3]]
            if xs:
                x0, x1, y0, y1 = min(x0, xs[0]), max(x1, xs[-1]), min(y0, y), max(y1, y)
    return x0, y0, x1 - x0 + 1, y1 - y0 + 1


BX, BY, BW, BH = bbox(FRAMES)

cpu = {"load": 0.0, "shown": 0.0, "frame": 0, "next": 0.0}
tap_at = [-9.0]


def cpu_sample():
    with open("/proc/stat") as f:
        v = [int(x) for x in f.readline().split()[1:]]
    idle = v[3] + (v[4] if len(v) > 4 else 0)
    return sum(v), idle


def poller():
    prev = cpu_sample()
    while True:
        time.sleep(0.5)
        try:
            cur = cpu_sample()
        except (OSError, ValueError):
            continue
        dt, di = cur[0] - prev[0], cur[1] - prev[1]
        prev = cur
        if dt > 0:
            load = max(0.0, min(1.0, 1 - di / dt))
            cpu["load"] = cpu["load"] * 0.6 + load * 0.4      # сглаживание: кот не дёргается от всплесков


def speed(load):
    return 3 + 17 * load            # кадров/с


started = [False]


def tick(host, now):
    if not started[0] and host.size:
        started[0] = True
        threading.Thread(target=poller, daemon=True).start()
    if now >= cpu["next"]:
        cpu["frame"] = (cpu["frame"] + 1) % len(FRAMES)
        cpu["next"] = now + 1 / speed(cpu["load"])
        cpu["shown"] = cpu["load"]
        with host.lock:
            host.dirty = True


def on_tap(host, x):
    tap_at[0] = time.monotonic(); host.animate(0.35)
    spawn(host.opts.get("command") or "yumi-sysmon")


def draw(host, c, w, h, theme, opts, now):
    pal, k = Pal(theme), host.intro()
    cell(c, 0, w, h, pal, k, tap_at[0], now)
    load = cpu["shown"]
    ink = pal.red if load > .95 else (pal.yellow if load > .85 else pal.accent)
    label = f"{round(load * 100)}%" if opts.get("pct") else ""
    lw = text_w(c, pal, "100%", 16) + 10 if label else 0
    sc = min((w - 16 - lw) / BW, (h - 14) / BH)
    cw, ch = BW * sc, BH * sc
    x0, y0 = (w - cw - lw) / 2, (h - ch) / 2
    c.save()
    c.translate(x0, y0); c.scale(sc, sc)
    c.set_source_rgba(*ink, k)
    c.mask_surface(FRAMES[cpu["frame"]], -BX, -BY)
    c.restore()
    if label:
        text(c, pal, label, 16, x0 + cw + 10, h, pal.fg, k)


if __name__ == "__main__":
    Host(on_tap).run(draw, tick)
