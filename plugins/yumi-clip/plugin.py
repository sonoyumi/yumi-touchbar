#!/usr/bin/env python3
"""Плагин touchbard «yumi-clip» (тачбар yumi, 19.10.2026): последние копии из cliphist чипами.

Слева значок — меню буфера Quickshell (как SUPER+V), дальше options.count (2) последних записей
`cliphist list`; касание по чипу — `cliphist decode <id> | wl-copy` (запись снова в буфере, можно вставлять).
Картинки — «картинка PNG …» со значком. Новые копии видны через ~1,5 с (опрос cliphist).
Опции: { plugin = "yumi-clip", flex = 1, options = { count = 2 } }
"""
import os, re, subprocess, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from yumi_glow_lib import Host
from yumi_cells import Pal, cell, glyph, text, fit, spawn, run

G_CLIP, G_IMG = "\U000F014D", "\U000F02E9"          # clipboard-text, image
MENU_W = 84
tap = {}                                           # индекс ячейки → время касания
items = []                                         # [(id, текст, картинка?)]


def read(n):
    out = []
    for line in run("cliphist", "list").splitlines()[:n]:
        cid, _, prev = line.partition("\t")
        m = re.match(r"\[\[ binary data .*?(\w+) (\d+x\d+) \]\]", prev)
        if m:
            out.append((cid, f"картинка {m.group(1).upper()} {m.group(2)}", True))
        else:
            out.append((cid, " ".join(prev.split()), False))
    return out


def poller(host):
    global items
    while True:
        new = read(int(host.opts.get("count", 2)))
        if new != items:
            items = new
            with host.lock:
                host.dirty = True
        time.sleep(1.5)


started = [False]


def tick(host, now):
    if not started[0] and host.size:
        started[0] = True
        threading.Thread(target=poller, args=(host,), daemon=True).start()


def layout(w, n):
    chips = max(1, n)
    cw = (w - MENU_W) / chips
    return [(0, 0, MENU_W)] + [(i + 1, MENU_W + i * cw, cw) for i in range(chips)]


def on_tap(host, x):
    w = (host.size or (0, 0))[0]
    for i, cx, cw in layout(w, len(items)):
        if cx <= x < cx + cw:
            tap[i] = time.monotonic(); host.animate(0.35)
            if i == 0:
                spawn(host.opts.get("command") or "qs -c yumi ipc call clipboard toggle center")
            elif i - 1 < len(items):
                subprocess.Popen(["sh", "-c", f"cliphist decode {items[i - 1][0]} | wl-copy"], start_new_session=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return


def draw(host, c, w, h, theme, opts, now):
    pal, k = Pal(theme), host.intro()
    for i, cx, cw in layout(w, len(items)):
        cell(c, cx, cw, h, pal, k, tap.get(i, -9), now)
        if i == 0:
            glyph(c, pal, G_CLIP, 26, cx + (cw - 26) / 2 - 2, h, pal.accent, k)
            continue
        if i - 1 >= len(items):
            text(c, pal, "буфер пуст", 15, cx + 16, h, pal.dim, k, bold=False)
            continue
        _, label, img = items[i - 1]
        x = cx + 16
        if img:
            x += glyph(c, pal, G_IMG, 20, x, h, pal.accent, k) + 8
        text(c, pal, fit(c, pal, label, 16, cx + cw - x - 14, bold=False), 16, x, h, pal.fg, k, bold=False)


Host(on_tap).run(draw, tick)
