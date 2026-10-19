#!/usr/bin/env python3
"""Плагин touchbard «yumi-pomodoro» (тачбар yumi, 19.10.2026): Pomodoro на всю ширину ячейки.

Полоса — сама таймер: заливка акцентом ползёт слева направо, поверх «Фокус 14:32 · круг 2 из 4».
Фокус 25 мин → перерыв 5 (каждый 4-й — 15) → снова фокус. Быстрые таймеры (yumi-timer) идут в этой же полосе.
Касание — старт / пауза; правый край (кнопка «сброс», 110 px) — сброс. Конец фазы — уведомление и мягкая
вспышка; следующая фаза ждёт касания (не стартует сама). Состояние — yumi_pomo_state (общий файл).
Опции: { plugin = "yumi-pomodoro", flex = 1 }
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from yumi_glow_lib import Host, rounded, mix, R, M
from yumi_cells import Pal, cell, glyph, text, spawn
import yumi_pomo_state as P

RESET_W = 110
G_PLAY, G_PAUSE, G_RESET = "\U000F040A", "\U000F03E4", "\U000F0453"   # play, pause, restore
NAMES = {"focus": "Фокус", "break": "Перерыв", "long": "Длинный перерыв", "timer": "Таймер"}
tap = {"main": -9.0, "reset": -9.0}
done_at = [-9.0]


checked = [0.0]


def tick(host, now):
    # конец фазы проверяем дважды в секунду; цифры обновляет кадр-«пульс» Host раз в 1 с
    if now - checked[0] < 0.5:
        return
    checked[0] = now
    d = P.load()
    if P.running(d) and P.left(d) <= 0:
        name = NAMES.get(d["mode"], "Таймер")
        P.save(P.next_phase(d))
        done_at[0] = time.monotonic(); host.animate(1.2)
        spawn(f"notify-send -a Тачбар -i alarm-symbolic 'Pomodoro' '{name}: время вышло'")


def on_tap(host, x):
    w = (host.size or (0, 0))[0]
    d = P.load()
    if x >= w - RESET_W:
        tap["reset"] = time.monotonic(); P.save(P.reset(d))
    else:
        tap["main"] = time.monotonic(); P.save(P.pause(d) if P.running(d) else P.start(d))
    host.animate(0.35)


def mmss(s):
    return f"{s // 60}:{s % 60:02d}"


def draw(host, c, w, h, theme, opts, now):
    pal, k = Pal(theme), host.intro()
    d = P.load()
    run_, left = P.running(d), P.left(d)
    mw = w - RESET_W
    flash = max(0.0, 1 - (now - done_at[0]) / 1.2)
    cell(c, 0, mw, h, pal, k, tap["main"], now, fill=mix(pal.surface, pal.accent, .5 * flash))
    frac = 1 - left / d["total"] if d["total"] else 0
    if frac > 0:
        rounded(c, 3, M, max(18, (mw - 6) * frac), h - 2 * M, R)
        c.set_source_rgba(*pal.accent, (.85 if run_ else .45) * k); c.fill()
    ink = pal.surface if run_ and frac > .25 else pal.fg
    x = 20
    x += glyph(c, pal, G_PAUSE if run_ else G_PLAY, 22, x, h, ink, k) + 12
    x += text(c, pal, NAMES.get(d["mode"], "Таймер") + ("" if run_ else " · пауза" if 0 < frac < 1 else ""), 18, x, h, ink, k) + 14
    x += text(c, pal, mmss(left), 20, x, h, ink, k) + 16
    if d["mode"] in ("focus", "break"):
        text(c, pal, f"круг {d['round']} из {P.ROUNDS}", 14, x, h, mix(ink, pal.dim, .4), k, bold=False)
    cell(c, mw, RESET_W, h, pal, k, tap["reset"], now)
    glyph(c, pal, G_RESET, 24, mw + (RESET_W - 24) / 2 - 2, h, pal.dim, k)


Host(on_tap).run(draw, tick)
