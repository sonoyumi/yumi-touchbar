#!/usr/bin/env python3
"""Плагин touchbard «yumi-anc» (тачбар yumi, 19.10.2026): режим AirPods — 4 ячейки, текущий подсвечен.

Выкл / Шумодав / Прозрачность / Адаптивный. Текущий режим — заливка акцентом (тёмные значок и подпись);
выбран, но наушники ещё не подтвердили — акцентная рамка. Источник — свой постоянный aap.Session через сокет
службы yumi-airpods (как меню AirPods; служба принимает несколько читателей), поэтому подсветка меняется и при
смене режима с ножки или с iPhone. Касание — sess.change(S_MODE, N) с подтверждением, как в меню.
Режим, запрещённый в настройках AirPods, — тусклый. Наушники не на связи — все ячейки тусклые, «нет связи».
Опции: { plugin = "yumi-anc", width = 560, options = { mac = "AA:BB:CC:DD:EE:FF" } }
(без mac — aap.default_mac(): ~/.config/yumi/airpods.conf или первые сопряжённые «AirPods»)
"""
import os, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.expanduser("~/.local/lib/yumi/panel"))
from yumi_glow_lib import Host, rounded, R, M
from yumi_cells import Pal, cell, glyph, text, text_w, fit
import aap  # noqa: E402

S_ALLOW_OFF = 0x34       # «разрешить режим Выкл» (iOS 18; проверено 19.10 на A3047: без него «Выкл» молча отбрасывается)
MODES = [(1, "\U000F07CE", "Выкл"), (2, "\U000F0498", "Шумодав"), (3, "\U000F070D", "Прозрачн."), (4, "\U000F0068", "Адаптив")]
tap = {}
st = {"status": "", "mode": None, "pending": False, "allowed": [1, 2, 3, 4], "allow_off": None}
sess = [None]


def on_update(host, snap):
    mode = snap["settings"].get(aap.S_MODE, [None])[0]
    new = {"status": snap["status"], "mode": mode, "pending": aap.S_MODE in snap["pending"],
           "allowed": list(snap.get("allowed") or [1, 2, 3, 4]),
           "allow_off": (snap["settings"].get(S_ALLOW_OFF) or [None])[0]}
    if new != st:
        st.update(new)
        with host.lock:
            host.dirty = True


started = [False]


def tick(host, now):
    if not started[0] and host.size:
        started[0] = True
        mac = host.opts.get("mac") or aap.default_mac() or ""
        sess[0] = aap.Session(mac, lambda snap: on_update(host, snap))
        sess[0].start()


def online():
    return st["status"] == "ok" and st["mode"] is not None


def on_tap(host, x):
    w = (host.size or (0, 0))[0]
    i = min(3, max(0, int(x / (w / 4))))
    tap[i] = time.monotonic(); host.animate(0.35)
    n = MODES[i][0]
    if sess[0] and online():
        if n == 1 and st.get("allow_off") != 1:
            # «Выкл» наушники принимают только с разрешением 0x34 = 1 и маской режимов с битом «Выкл»
            # (как «Режимы прослушивания → Выкл» на iPhone); сняли с iPhone/сбросили — включаем снова
            sess[0].change(S_ALLOW_OFF, 0x01)
            sess[0].change(aap.S_ALLOWED, 0x0F)
        sess[0].change(aap.S_MODE, n)


def draw(host, c, w, h, theme, opts, now):
    pal, k = Pal(theme), host.intro()
    cw = w / 4
    on = online()
    for i, (n, g, label) in enumerate(MODES):
        x = i * cw
        active = on and st["mode"] == n
        allowed = on and n in st["allowed"]
        if active and not st["pending"]:
            cell(c, x, cw, h, pal, k, tap.get(i, -9), now, fill=pal.accent)
            ink, sub = pal.surface, pal.surface
        else:
            cell(c, x, cw, h, pal, k, tap.get(i, -9), now)
            ink, sub = (pal.accent, pal.fg) if allowed else (pal.dim, pal.dim)
            if active:                          # выбран, ждём подтверждения наушников — рамка акцентом
                rounded(c, x + 4.5, M + 1.5, cw - 9, h - 2 * M - 3, R - 1.5)
                c.set_source_rgba(*pal.accent, k); c.set_line_width(2.5); c.stroke()
        if not on and i == 0 and st["status"]:
            label = "нет связи"
        gw = text_w(c, pal, g, 24, bold=False)
        lab = fit(c, pal, label, 16, cw - gw - 30)
        total = gw + 9 + text_w(c, pal, lab, 16)
        tx = x + (cw - total) / 2
        tx += glyph(c, pal, g, 24, tx, h, ink, k) + 9
        text(c, pal, lab, 16, tx, h, sub, k)


Host(on_tap).run(draw, tick)
