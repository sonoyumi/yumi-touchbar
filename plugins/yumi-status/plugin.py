#!/usr/bin/env python3
"""Плагин touchbard «yumi-status» (тачбар yumi, 16.10.2026): ряд «пульта» с живым состоянием.

Ячейки (по умолчанию wifi, vpn, bt, battery): значок + короткая подпись (сеть, VPN, наушники, проценты).
Включено — значок акцентом, выключено — тусклый. Данные читает фоновый поток раз в 3 с (nmcli, bluetoothctl,
/sys/class/power_supply) — первый кадр приходит сразу, с «…». Касание — вспышка и меню Quickshell
(Wi-Fi, VPN, Bluetooth, питание); свои команды — options.commands = { wifi = "…" }.
Опции: { plugin = "yumi-status", width = 560, options = { cells = ["wifi", "vpn", "bt", "battery"] } }
"""
import glob, os, subprocess, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from yumi_glow_lib import Host, rgb, mix, rounded, R, M, pill, face
import cairo

QS = "qs -c yumi ipc call menu center "
COMMANDS = {"wifi": QS + "wifi", "vpn": QS + "vpn", "bt": QS + "bluetooth", "battery": QS + "power"}
GLYPH = {"wifi": ("\U000F05A9", "\U000F05AA"), "vpn": ("\U000F0582", "\U000F0582"),
         "bt": ("\U000F00AF", "\U000F00B2"), "battery": ("\U000F0079", "\U000F0079")}
FLASH = 0.35
tapped = {}
data = {k: (None, "…") for k in GLYPH}              # ячейка → (вкл/выкл/None, подпись)


def run(*cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=3).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def short(s, n=11):
    s = s.strip()
    return s if len(s) <= n else s[:n - 1] + "…"


def read():
    out = {}
    wifi, vpn = None, None
    for line in run("nmcli", "-t", "-f", "TYPE,STATE,CONNECTION", "device").splitlines():
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        typ, state, conn = parts
        if typ == "wifi" and wifi is None:
            wifi = conn if state.startswith("connected") else ""
        # Tailscale (tun, всегда включён ради ssh) — не VPN-выход в интернет, его не показываем
        if typ in ("wireguard", "tun", "vpn") and state.startswith("connected") and conn \
                and "tailscale" not in conn.lower():
            vpn = conn
    out["wifi"] = (bool(wifi), short(wifi) if wifi else "нет сети")
    out["vpn"] = (bool(vpn), short(vpn.removeprefix("VPN ").strip() or "VPN") if vpn else "выкл")
    show = run("bluetoothctl", "show")
    on = "Powered: yes" in show
    dev = ""
    if on:
        for line in run("bluetoothctl", "devices", "Connected").splitlines():
            p = line.split(" ", 2)
            if len(p) == 3:
                dev = p[2]; break
    out["bt"] = (on, short(dev) if dev else ("вкл" if on else "выкл"))
    cap, status = None, ""
    # 19.10: только батарея ноутбука (scope System). Раньше брали первую «Battery» в списке —
    # это была мышь Logitech (hidpp_battery_0, scope Device) → чужой заряд
    for d in sorted(glob.glob("/sys/class/power_supply/*"), key=lambda d: "macsmc" not in d):
        try:
            if open(f"{d}/type").read().strip() != "Battery":
                continue
            try:
                scope = open(f"{d}/scope").read().strip()
            except OSError:
                scope = ""
            if scope == "Device":
                continue
            cap = int(open(f"{d}/capacity").read()); status = open(f"{d}/status").read().strip(); break
        except (OSError, ValueError):
            pass
    if cap is not None:
        out["battery"] = (status in ("Charging", "Full") or cap > 20, f"{cap}%")   # зарядка — значком (⚡ в Noto Serif нет — был квадратик)
        out["battery_level"] = cap
        out["battery_charging"] = status == "Charging"
    return out


def poller(host):
    while True:
        new = read()
        changed = any(data.get(k) != v for k, v in new.items())
        data.update(new)
        if changed:
            with host.lock:
                host.dirty = True
        time.sleep(3.0)


started = [False]


def tick(host, now):
    if not started[0] and host.size:
        started[0] = True
        threading.Thread(target=poller, args=(host,), daemon=True).start()


def cells(host_or_opts, w):
    names = [c for c in (host_or_opts.get("cells") or ["wifi", "vpn", "bt", "battery"]) if c in GLYPH]
    n = len(names)
    return [(names[i], i * w / n, w / n) for i in range(n)]


def on_tap(host, x):
    w = (host.size or (0, 0))[0]
    for i, (name, cx, cw) in enumerate(cells(host.opts, w)):
        if cx <= x < cx + cw:
            tapped[i] = time.monotonic(); host.animate(FLASH)
            cmd = (host.opts.get("commands") or {}).get(name) or COMMANDS[name]
            subprocess.Popen(["sh", "-c", cmd], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return


def battery_glyph(level):
    if level is None:
        return "\U000F0079"
    steps = ["\U000F007A", "\U000F007B", "\U000F007C", "\U000F007D", "\U000F007E", "\U000F007F", "\U000F0080",
             "\U000F0081", "\U000F0082", "\U000F0079"]                 # battery-10 … battery (100)
    return steps[min(9, max(0, round(level / 10) - 1))]


def draw(host, c, w, h, theme, opts, now):
    accent, fg = rgb(theme.get("accent"), "#f2a07b"), rgb(theme.get("fg"), "#f3ece7")
    surface, dim = rgb(theme.get("surface"), "#16242a"), rgb(theme.get("fg_dim"), "#8c9ca6")
    red = rgb(theme.get("red"), "#ed8796")
    font = theme.get("font") or "JetBrainsMono Nerd Font"
    k, gap = host.intro(), 8.0
    for i, (name, cx, cw) in enumerate(cells(opts, w)):
        on, label = data.get(name, (None, "…"))
        f = max(0.0, 1 - (now - tapped.get(i, -9)) / FLASH)
        pill(c, cx + gap / 2, M, cw - gap, h - 2 * M, theme, mix(surface, accent, .45 * f), k)
        g = GLYPH[name][0 if on is not False else 1]
        if name == "battery":
            g = "\U000F0084" if data.get("battery_charging") else battery_glyph(data.get("battery_level"))   # battery-charging
        ink = accent if on else dim
        if name == "battery" and on is False:
            ink = red
        c.select_font_face(font, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL); c.set_font_size(30)
        ge = c.text_extents(g)
        face(c, theme, label, 17)
        room = cw - gap - 24 - ge.width - 10                     # подпись не шире ячейки — иначе «…»
        while label and c.text_extents(label).x_advance > room and len(label) > 2:
            label = label[:-2] + "…"
        te = c.text_extents(label)
        total = ge.width + 10 + te.x_advance
        x0 = cx + (cw - total) / 2
        c.select_font_face(font, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL); c.set_font_size(30)
        c.move_to(x0 - ge.x_bearing, h / 2 - ge.height / 2 - ge.y_bearing)
        c.set_source_rgba(*ink, k); c.show_text(g)
        face(c, theme, label, 17)
        c.move_to(x0 + ge.width + 10, h / 2 - te.height / 2 - te.y_bearing)
        c.set_source_rgba(*(fg if on else mix(dim, fg, .3)), k); c.show_text(label)


Host(on_tap).run(draw, tick)
