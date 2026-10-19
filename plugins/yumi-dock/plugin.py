#!/usr/bin/env python3
"""Плагин touchbard «yumi-dock» (тачбар yumi, 16.10.2026): «папка» без подписей — больше приложений в ряд.

Как yumi-apps, но только иконки (подписи — по желанию, labels = true): ячейки фиксированной ширины (cell) по центру
или поровну на всю ширину (cell = 0). Под запущенным приложением — короткая акцентная черта (как точка в доке macOS):
раз в 2 с фоновый поток читает `hyprctl -j clients`. Касание: приложение запущено и focus = true — фокус на его окно
(hyprctl dispatch hl.dsp.focus, как меню рабочих столов), иначе — command. Вспышка акцентом 0,35 с.
Иконки — yumi_icons (тема GTK, как меню приложений); ещё не готовые в кэше рисуются в фоне, первый кадр — сразу.
Опции: { plugin = "yumi-dock", options = { px = 38, cell = 92, labels = false, running = true, focus = true, apps = [
           { icon = "org.kde.dolphin", command = "dolphin", class = "dolphin", label = "Файлы" }, … ] } }
  class — регулярное выражение класса окна (без учёта регистра); по умолчанию — имя иконки.
"""
import json, os, re, subprocess, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from yumi_glow_lib import Host, rgb, mix, rounded, R, M, pill, face
import yumi_icons
import cairo

FLASH = 0.35
tapped = {}                       # индекс → время касания
st = {"clients": [], "loading": set(), "queue": [], "loader": False, "drawn": False, "poll": False}
lock = threading.Lock()


def layout(w, n, cell):
    """Ячейки (x, ширина): фиксированные по центру, или поровну, если не влезают / cell = 0."""
    if not n:
        return []
    if cell and cell * n <= w:
        x0 = (w - cell * n) / 2
        return [(x0 + i * cell, cell) for i in range(n)]
    return [(i * w / n, w / n) for i in range(n)]


def pattern(a):
    if a.get("class"):
        return a["class"]
    name = os.path.basename(a.get("icon", "")).split(".")[-1]
    return re.escape(name) if name else "^$"


def window_of(a):
    pat = pattern(a)
    with lock:
        for c in st["clients"]:
            if re.search(pat, c.get("class") or "", re.I):
                return c.get("address")
    return None


def poller(host):
    while True:
        try:
            out = subprocess.run(["hyprctl", "-j", "clients"], capture_output=True, text=True, timeout=2).stdout
            cl = [{"class": c.get("class", ""), "address": c.get("address", "")} for c in json.loads(out or "[]")
                  if c.get("mapped", True)]
        except (OSError, ValueError, subprocess.TimeoutExpired):
            cl = []
        with lock:
            changed = [c["class"] for c in cl] != [c["class"] for c in st["clients"]]
            st["clients"] = cl
        if changed:
            with host.lock:
                host.dirty = True
        time.sleep(2.0)


def icon(host, name, px):
    """Иконка, если уже в памяти или в кэше-PNG; иначе — в очередь фоновой загрузки (кадр не ждёт SVG)."""
    key = (name, px)
    if key in yumi_icons._cache:
        return yumi_icons._cache[key]
    base = os.path.join(yumi_icons.CACHE, f"{name.replace('/', '_')}-{px}")
    if os.path.exists(base + ".png"):
        return yumi_icons.surface(name, px)
    if os.path.exists(base + ".none"):              # не нашлась в теме в прошлый раз — не искать при каждом запуске
        yumi_icons._cache[key] = None
        return None
    if key not in st["loading"]:
        st["loading"].add(key); st["queue"].append(key)
    return None


def loader(host):
    """Один поток, по очереди (SVG через librsvg + поиск по теме ≈ 0,1–0,4 с на иконку) — только после первого кадра."""
    while st["queue"]:
        name, px = st["queue"].pop(0)
        s = None
        try:
            s = yumi_icons.surface(name, px)
        except Exception:
            pass
        if s is None:
            try:
                os.makedirs(yumi_icons.CACHE, exist_ok=True)
                open(os.path.join(yumi_icons.CACHE, f"{name.replace('/', '_')}-{px}.none"), "w").close()
            except OSError:
                pass
        with host.lock:
            host.dirty = True
    st["loader"] = False


def on_tap(host, x):
    apps = host.opts.get("apps") or []
    w = (host.size or (0, 0))[0]
    for i, (cx, cw) in enumerate(layout(w, len(apps), float(host.opts.get("cell", 92)))):
        if cx <= x < cx + cw:
            tapped[i] = time.monotonic(); host.animate(FLASH)
            a = apps[i]
            addr = window_of(a) if host.opts.get("focus", True) else None
            if addr:
                cmd = ["hyprctl", "dispatch", f'hl.dsp.focus({{ window = "address:{addr}" }})']
            elif a.get("command"):
                cmd = ["sh", "-c", a["command"]]
            else:
                return
            subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return


def tick(host, now):
    if not st["drawn"]:
        return                                          # сначала кадр, потом фоновая работа
    if not st["poll"] and host.size and host.opts.get("running", True):
        st["poll"] = True
        threading.Thread(target=poller, args=(host,), daemon=True).start()
    if st["queue"] and not st["loader"]:
        st["loader"] = True
        threading.Thread(target=loader, args=(host,), daemon=True).start()


def draw(host, c, w, h, theme, opts, now):
    accent, fg = rgb(theme.get("accent"), "#f2a07b"), rgb(theme.get("fg"), "#f3ece7")
    surface, hi = rgb(theme.get("surface"), "#16242a"), rgb(theme.get("surface_hi"), "#305861")
    k = host.intro()
    st["drawn"] = True
    apps = opts.get("apps") or []
    px, gap = int(opts.get("px", 38)), 8.0
    labels, pills = bool(opts.get("labels", False)), opts.get("pills", True)
    fpx = float(opts.get("font_px", 16))
    if labels:
        face(c, theme, "Aa", fpx)
    for i, (cx, cw) in enumerate(layout(w, len(apps), float(opts.get("cell", 92)))):
        a = apps[i]
        f = max(0.0, 1 - (now - tapped.get(i, -9)) / FLASH)
        if pills or f > 0:
            if pills:
                pill(c, cx + gap / 2, M, cw - gap, h - 2 * M, theme, mix(surface, accent, .45 * f), k)
            else:
                rounded(c, cx + gap / 2, M, cw - gap, h - 2 * M, R)
                c.set_source_rgba(*mix((0, 0, 0), accent, .45 * f), .6 * f); c.fill()
        label = a.get("label", "") if labels else ""
        e = c.text_extents(label) if label else None
        total = px + (8 + e.x_advance if label else 0)
        x0, y0 = cx + (cw - total) / 2, (h - px) / 2 - 2
        s = icon(host, a.get("icon", ""), px)
        if s is not None:
            c.save(); c.set_source_surface(s, x0, y0); c.paint_with_alpha(k); c.restore()
        else:                                               # иконка ещё рисуется в фоне — мягкий квадрат
            rounded(c, x0 + 3, y0 + 3, px - 6, px - 6, 8); c.set_source_rgba(*hi, .55 * k); c.fill()
        if label:
            c.move_to(x0 + px + 8, h / 2 - e.height / 2 - e.y_bearing); c.set_source_rgba(*fg, k); c.show_text(label)
        if opts.get("running", True) and window_of(a):       # черта «запущено» под иконкой
            rounded(c, cx + cw / 2 - 7, h - M - 6, 14, 3, 1.5); c.set_source_rgba(*accent, .95 * k); c.fill()


Host(on_tap).run(draw, tick)
