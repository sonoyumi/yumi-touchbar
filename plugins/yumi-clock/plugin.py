#!/usr/bin/env python3
"""Плагин touchbard «yumi-clock» (стиль yumi-boot, 16.10.2026): маленькие часы со свечением.
Опции: { plugin = "yumi-clock", width = 96, options = { format = "%H:%M", px = 24,
          command = "qs -c yumi ipc call menu center calendar" } }
Кадр: раз в секунду (иначе touchbard покажет заглушку), смена минуты — сразу; касание — вспышка 0,35 с + команда."""
import os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from yumi_glow_lib import Host, rgb, mix, rounded, glow_text, R, M, pill, face, split_font, outline

FLASH = 0.35
tapped = [0.0]


def on_tap(host, x):
    tapped[0] = time.monotonic(); host.animate(FLASH)
    cmd = host.opts.get("command")
    if cmd:
        subprocess.Popen(["sh", "-c", cmd], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def draw(host, c, w, h, theme, opts, now):
    accent, fg = rgb(theme.get("accent"), "#f2a07b"), rgb(theme.get("fg"), "#f3ece7")
    k = host.intro()
    f = max(0.0, 1 - (now - tapped[0]) / FLASH) if tapped[0] else 0.0
    if outline(theme):                          # yumi (19.10): «капсулы» — часы тоже в рамке
        pill(c, 3, M, w - 6, h - 2 * M, theme, rgb(theme.get("surface"), "#16242a"), k)
    if f > 0:                                   # отклик на касание — как PRESS_FADE у кнопок touchbard
        rounded(c, 0, M, w, h - 2 * M, R); c.set_source_rgba(*accent, .30 * f); c.fill()
    text = time.strftime(opts.get("format", "%H:%M"))
    ink = mix(fg, accent, .30)
    font = opts.get("font") or split_font(theme)[0]
    glow_text(c, text, font, float(opts.get("px", 24)),
              w / 2, h / 2, mix((0, 0, 0), ink, k), accent, (.9 * k + .6 * f) * (.4 if outline(theme) else 1),
              bold=not outline(theme))


minute = [time.strftime("%H%M")]


def tick(host, now):
    m = time.strftime("%H%M")
    if m != minute[0]:
        minute[0] = m
        with host.lock:
            host.dirty = True


Host(on_tap).run(draw, tick)
