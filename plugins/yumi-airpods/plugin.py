#!/usr/bin/env python3
"""Плагин touchbard «yumi-airpods» (тачбар yumi, 19.10.2026): заряд AirPods — левый, правый, кейс.

Источник тот же, что у пилюли бара (~/.local/lib/yumi/bar/airpods): сокет службы yumi-airpods
($XDG_RUNTIME_DIR/yumi-airpods-<MAC>.sock, служба принимает несколько читателей). Только ЧИТАЕМ: всё,
что пишется в сокет, уходит наушникам. Кейс закрыт — последний известный заряд с «N мин» (aap.with_last_case).
Наушники не подключены — тусклое «не подключены». ≤ 20 % — жёлтым, ≤ 10 % — красным, заряжается — 󱐋.
Касание — меню AirPods Quickshell; своя команда — options.command.
Опции: { plugin = "yumi-airpods", width = 330 }
"""
import glob, os, select, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.expanduser("~/.local/lib/yumi/panel"))
from yumi_glow_lib import Host
from yumi_cells import Pal, cell, glyph, text, text_w, fit, spawn
import aap  # noqa: E402

RUN = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
G_BUDS, G_CASE, G_BOLT = "\U000F02CB", "\U000F0E45", "\U000F140B"   # headphones, package (кейс), молния
PARTS = (("left", "L"), ("right", "R"), ("case", "кейс"))
tap_at = [-9.0]
state = {"on": False, "battery": {}}


def watch(host, path):
    mac = ":".join(path.rsplit("-", 1)[1].split(".")[0][i:i + 2] for i in range(0, 12, 2))
    s = aap.open_relay(mac)
    if s is None:
        return
    st = aap.State()
    state.update(on=True, battery=aap.with_last_case(mac, {}))
    with host.lock:
        host.dirty = True
    try:
        while True:
            ready, _, _ = select.select([s], [], [], 5)
            if not ready:
                if not os.path.exists(path):
                    return
                continue
            data = s.recv(8192)
            if not data:
                return
            if st.handle(data) and data[4:6] == aap.OP_BATTERY.to_bytes(2, "little"):
                state["battery"] = aap.with_last_case(mac, st.battery)
                with host.lock:
                    host.dirty = True
    except OSError:
        return
    finally:
        s.close()


def poller(host):
    while True:
        socks = sorted(glob.glob(os.path.join(RUN, "yumi-airpods-*.sock")))
        if socks:
            watch(host, socks[0])
        if state["on"]:
            state.update(on=False, battery={})
            with host.lock:
                host.dirty = True
        time.sleep(2)


started = [False]


def tick(host, now):
    if not started[0] and host.size:
        started[0] = True
        threading.Thread(target=poller, args=(host,), daemon=True).start()


def on_tap(host, x):
    tap_at[0] = time.monotonic(); host.animate(0.35)
    spawn(host.opts.get("command") or "qs -c yumi ipc call airpods toggle 0")


def draw(host, c, w, h, theme, opts, now):
    pal, k = Pal(theme), host.intro()
    cell(c, 0, w, h, pal, k, tap_at[0], now)
    x = 16
    if not state["on"]:
        x += glyph(c, pal, G_BUDS, 28, x, h, pal.dim, k) + 12
        text(c, pal, fit(c, pal, "AirPods не подключены", 16, w - x - 12), 16, x, h, pal.dim, k)
        return
    x += glyph(c, pal, G_BUDS, 28, x, h, pal.accent, k) + 10
    bat = state["battery"]
    shown = [(key, name, bat.get(key)) for key, name in PARTS
             if bat.get(key) and bat[key].get("available") and 0 <= bat[key].get("level", -1) <= 100]
    if not shown:
        text(c, pal, "заряд: ждём данные", 16, x, h, pal.dim, k)
        return
    room = (w - x - 8) / len(shown)
    for i, (key, name, b) in enumerate(shown):
        cx = x + i * room
        lvl, ch = b["level"], b.get("status") == "charging"
        ink = pal.red if lvl <= 10 else (pal.yellow if lvl <= 20 else pal.fg)
        if key == "case":
            ink = pal.dim if b.get("last") else ink
            glyph(c, pal, G_CASE, 18, cx, h, pal.dim, k)
            cx += 24
        else:
            cx += text(c, pal, name, 14, cx, h, pal.dim, k) + 6
        cx += text(c, pal, f"{lvl}", 19, cx, h, ink, k)
        if ch:
            glyph(c, pal, G_BOLT, 16, cx + 3, h, pal.accent, k)
        elif key == "case" and b.get("last") and b.get("ago"):
            text(c, pal, b["ago"], 11, cx + 5, h, pal.dim, k, bold=False)


Host(on_tap).run(draw, tick)
