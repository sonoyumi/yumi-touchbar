#!/usr/bin/env python3
"""Плагин touchbard «yumi-caffeine» (стиль yumi-boot, 16.10.2026): ☕ «не засыпать» с живым состоянием.
Выключено — тёмная таблетка, как кнопки бара; включено — таблетка с акцентной каймой и свечением,
при переключении — «вдох» свечения 0,9 с. Состояние: PID-файл yumi-caffeine (без запуска скрипта),
касание — `yumi-caffeine toggle` (общий для Waybar/Quickshell/SSH, с flock)."""
import math, os, subprocess, sys, time
import cairo
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from yumi_glow_lib import Host, rgb, mix, rounded, R, M, pill, face

CAF = os.path.expanduser("~/.local/bin/yumi-caffeine")
PIDF = os.path.join(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"), "yumi-caffeine.pid")
PULSE = 0.9
st = {"on": None, "at": 0.0, "poll": 0.0}


def caffeine_on():
    try:
        os.kill(int(open(PIDF).read().strip()), 0)
        return True
    except (OSError, ValueError):
        return False


def on_tap(host, x):
    with host.lock:
        st["on"] = not st["on"]; st["at"] = time.monotonic(); st["poll"] = time.monotonic() + 1.5
    host.animate(PULSE)
    subprocess.Popen([CAF, "toggle"], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def tick(host, now):
    if now < st["poll"]:
        return
    st["poll"] = now + 1.0
    on = caffeine_on()
    if on != st["on"]:
        first = st["on"] is None
        st["on"] = on; st["at"] = 0.0 if first else now
        if not first:
            host.animate(PULSE)
        with host.lock:
            host.dirty = True


def draw(host, c, w, h, theme, opts, now):
    accent, fg = rgb(theme.get("accent"), "#f2a07b"), rgb(theme.get("fg"), "#f3ece7")
    surface, bg = rgb(theme.get("surface"), "#16242a"), rgb(theme.get("bg"), "#000000")
    on, k = bool(st["on"]), host.intro()
    p = (now - st["at"]) / PULSE if st["at"] else 1.0
    breath = math.sin(math.pi * min(1.0, max(0.0, p))) if p < 1 else 0.0     # 0 → 1 → 0
    y, hh = M, h - 2 * M
    pill(c, 0, y, w, hh, theme, mix(surface, accent, .22) if on else surface)
    if on:
        g = .55 * k + .45 * breath                                          # свечение внутри таблетки
        rg = cairo.RadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w * .6)
        rg.add_color_stop_rgba(0, *accent, .35 * g); rg.add_color_stop_rgba(1, *accent, 0)
        rounded(c, 0, y, w, hh, R); c.set_source(rg); c.fill()
        for lw, a in ((5, .10), (3, .22), (1.5, .85)):                       # кайма с ореолом
            rounded(c, lw / 2, y + lw / 2, w - lw, hh - lw, R - lw / 2)
            c.set_source_rgba(*accent, a * (.6 + .4 * g)); c.set_line_width(lw); c.stroke()
    elif breath > 0:                                                         # «выдох» при выключении
        rounded(c, 0, y, w, hh, R); c.set_source_rgba(*accent, .25 * breath); c.fill()
    c.select_font_face(theme.get("font") or "JetBrainsMono Nerd Font")
    c.set_font_size(h * .5)
    glyph = "\U000F0176" if on else "\U000F0FAA"                              # coffee / coffee-off-outline
    e = c.text_extents(glyph)
    c.move_to((w - e.width) / 2 - e.x_bearing, (h - e.height) / 2 - e.y_bearing)
    c.set_source_rgb(*(mix(accent, (1, 1, 1), .25) if on else mix(bg, fg, .85))); c.show_text(glyph)


Host(on_tap).run(draw, tick)
