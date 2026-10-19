#!/usr/bin/env python3
"""Плагин touchbard «yumi-row» (тачбар yumi, 19.10.2026): ряд кнопок «значок + подпись» читаемого размера.

Зачем: у кнопок touchbard подпись 32 px жирным — в 150–170 px слово со значком не влезает. Здесь значок
24 px + подпись 16–17 px (как у yumi-status), подпись сама ужимается до 13 px, потом «…».
Касание — команда кнопки (как бинд Hyprland) и вспышка. Без подписи — только значок по центру.
Один плагин = одна ячейка на слое (touchbard различает плагины по имени), поэтому есть копии
yumi-row2 / yumi-row3 — тот же код (plugin.py — ссылка), чтобы поставить несколько рядов на один слой.
Опции: { plugin = "yumi-row", width = 360, options = { buttons = [
           { icon = "󰩭", label = "Область", command = "yumi-screenshot s" },
           { icon = "󰍹", label = "Экран", command = "yumi-screenshot m", w = 1 } ] } }
  w — доля ширины (по умолчанию 1); dim = true — значок тусклым.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from yumi_glow_lib import Host
from yumi_cells import Pal, cell, glyph, text, text_w, fit, spawn

ICON_PX, LABEL_PX, MIN_PX, GAP = 24, 17, 13, 9
tap = {}


def cells(opts, w):
    bs = [b for b in (opts.get("buttons") or []) if isinstance(b, dict)]
    total = sum(float(b.get("w", 1)) for b in bs) or 1
    out, x = [], 0.0
    for i, b in enumerate(bs):
        cw = w * float(b.get("w", 1)) / total
        out.append((i, b, x, cw)); x += cw
    return out


def on_tap(host, x):
    w = (host.size or (0, 0))[0]
    for i, b, cx, cw in cells(host.opts, w):
        if cx <= x < cx + cw:
            tap[i] = time.monotonic(); host.animate(0.35)
            if b.get("command"):
                spawn(b["command"])
            return


def draw(host, c, w, h, theme, opts, now):
    pal, k = Pal(theme), host.intro()
    for i, b, cx, cw in cells(opts, w):
        cell(c, cx, cw, h, pal, k, tap.get(i, -9), now)
        ink = pal.dim if b.get("dim") else pal.accent
        icon, label = b.get("icon") or "", b.get("label") or ""
        iw = text_w(c, pal, icon, ICON_PX, bold=False) if icon else 0
        if not label:
            glyph(c, pal, icon, ICON_PX, cx + (cw - iw) / 2, h, ink, k)
            continue
        room = cw - 24 - (iw + GAP if icon else 0)
        px = LABEL_PX
        while px > MIN_PX and text_w(c, pal, label, px) > room:
            px -= 1
        label = fit(c, pal, label, px, room)
        total = (iw + GAP if icon else 0) + text_w(c, pal, label, px)
        x = cx + (cw - total) / 2
        if icon:
            x += glyph(c, pal, icon, ICON_PX, x, h, ink, k) + GAP
        text(c, pal, label, px, x, h, pal.fg, k)


Host(on_tap).run(draw)
