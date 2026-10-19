"""Общие функции плагинов yumi-clock и yumi-caffeine (стиль тачбара «yumi-boot», 16.10.2026).

Рисует как загрузочная заставка Touch Bar: чёрный фон, скругление 9 px (у кнопок touchbard — тоже 9),
мягкое свечение акцентом. Свечение — не размытие, а несколько обводок с убывающей прозрачностью
(дёшево: кадр 96×60 рисуется < 1 мс).

Протокол touchbard (JSON по строкам): вход size/theme/cmd, выход frame + BGRA (premultiplied).
ВАЖНО: touchbard считает кадр плагина устаревшим через 1,5 с (PIXELS_STALE) и рисует вместо него
заглушку с именем плагина, поэтому кадр нужно повторять не реже раза в секунду (HEARTBEAT).
"""
import json, math, os, sys, threading, time
import cairo

HEARTBEAT = 1.0          # с; меньше 1,5 с из touchbard (ui.rs PIXELS_STALE)
INTRO = 0.2              # с (19.10: было 0.8 — после перезапуска плагин «проявлялся» почти секунду, казалось лагом); проявление свечения при появлении плагина (как «проявление» на заставке)
INTRO_FPS = 24
R, M = 9.0, 2.0          # радиус и поле сверху/снизу, как у кнопок touchbard (render.rs RADIUS, MARGIN_Y)

out = sys.stdout.buffer


def rgb(h, d="#ffffff"):
    h = (h if isinstance(h, str) and h.startswith("#") else d).lstrip("#")
    try:
        return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return rgb(d)


def mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


ICON_FONT = "JetBrainsMono Nerd Font"


def is_icon(s):
    """Строка со значком Nerd Font (частная область Unicode) — рисовать шрифтом значков."""
    return any(0xE000 <= ord(ch) <= 0xF8FF or ord(ch) >= 0xF0000 for ch in s)


def split_font(theme):
    """yumi (19.10): тема может дать список «Noto Serif, JetBrainsMono Nerd Font» (так понимает демон, pango).
    cairo в плагинах знает один шрифт — текст первым, значки шрифтом с «Nerd» в названии."""
    raw = theme.get("font") or ICON_FONT
    parts = [p.strip() for p in raw.split(",") if p.strip()] or [ICON_FONT]
    icon = next((p for p in parts if "Nerd" in p or p.endswith(" NF")), ICON_FONT)
    return theme.get("text_font") or parts[0], icon


def outline(theme):
    return theme.get("pill_style") == "outline"


def face(c, theme, s, px, bold=True):
    """Выбрать шрифт для строки s: значок — Nerd Font, текст — шрифт темы (в «капсулах» без жирного)."""
    text_font, icon_font = split_font(theme)
    icon = is_icon(s)
    heavy = bold and not icon and not outline(theme)
    c.select_font_face(icon_font if icon else text_font, cairo.FONT_SLANT_NORMAL,
                       cairo.FONT_WEIGHT_BOLD if heavy else cairo.FONT_WEIGHT_NORMAL)
    c.set_font_size(px)


def pill(c, x, y, w, h, theme, fill, k=1.0, r=None):
    """Фон ячейки. «Капсулы» (pill_style = outline): прозрачная с рамкой 1 px, выделенная — заливка 55 %."""
    r = R if r is None else r
    if outline(theme):
        surface, fg = rgb(theme.get("surface"), "#16242a"), rgb(theme.get("fg"), "#f3ece7")
        rounded(c, x + .5, y + .5, w - 1, h - 1, r)
        if sum(abs(a - b) for a, b in zip(fill, surface)) > .02:
            c.set_source_rgba(*fill, .55 * k)
        else:
            c.set_source_rgba(*fg, .035 * k)
        c.fill_preserve()
        c.set_source_rgba(*fg, .16 * k); c.set_line_width(1); c.stroke()
    else:
        rounded(c, x, y, w, h, r)
        c.set_source_rgba(*fill, k); c.fill()


def rounded(c, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    c.new_sub_path()
    c.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    c.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    c.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    c.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    c.close_path()


def glow_text(c, text, font, px, cx, cy, ink, glow, strength, bold=True):
    """Текст с мягким ореолом: 4 обводки контура (шире → прозрачнее), потом заливка."""
    c.select_font_face(font, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    c.set_font_size(px)
    e = c.text_extents(text)
    x, y = cx - e.width / 2 - e.x_bearing, cy - e.height / 2 - e.y_bearing
    if strength > 0:
        for lw, a in ((12, .05), (8, .08), (5, .12), (2.5, .18)):
            c.move_to(x, y); c.text_path(text)
            c.set_source_rgba(*glow, a * strength); c.set_line_width(lw); c.set_line_join(cairo.LINE_JOIN_ROUND)
            c.stroke()
    c.move_to(x, y); c.text_path(text)
    c.set_source_rgb(*ink); c.fill()


def emit(w, h, painter):
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    c = cairo.Context(s)
    fo = cairo.FontOptions(); fo.set_antialias(cairo.ANTIALIAS_GRAY); c.set_font_options(fo)
    painter(c, w, h)
    s.flush()
    data = bytes(s.get_data())        # ARGB32 на little-endian = BGRA с предумноженной альфой
    try:
        out.write((json.dumps({"t": "frame", "w": w, "h": h, "len": len(data)}) + "\n").encode())
        out.write(data); out.flush()
    except BrokenPipeError:
        os._exit(0)


def log(msg):
    try:
        out.write((json.dumps({"t": "log", "msg": msg}, ensure_ascii=False) + "\n").encode()); out.flush()
    except BrokenPipeError:
        os._exit(0)


class Host:
    """Цикл плагина: читает stdin в потоке, перерисовывает по событию, по анимации и раз в HEARTBEAT."""

    def __init__(self, on_tap=None):
        self.lock = threading.Lock()
        self.size, self.opts, self.theme = None, {}, {}
        self.dirty, self.anim_until, self.born = True, 0.0, None
        self.on_tap = on_tap

    def animate(self, secs):
        with self.lock:
            self.anim_until = max(self.anim_until, time.monotonic() + secs); self.dirty = True

    def reader(self):
        for line in sys.stdin:
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            t = msg.get("t")
            with self.lock:
                if t == "size":
                    self.size = (int(msg.get("w", 0)), int(msg.get("h", 0)))
                    self.opts = msg.get("options") or {}
                    if self.born is None:
                        self.born = time.monotonic(); self.anim_until = self.born + INTRO
                    self.dirty = True
                elif t == "theme":
                    text_font, icon_font = split_font(msg)
                    msg = dict(msg, text_font=text_font, font=icon_font)   # yumi (19.10): см. split_font
                    self.theme = msg; self.dirty = True
            if t == "cmd" and msg.get("cmd") == "tap" and self.on_tap:
                self.on_tap(self, msg.get("x", 0))
        os._exit(0)                    # агент закрыл stdin — выходим

    def intro(self):
        """0…1 — проявление после появления (ease-out), как полоска и точки на заставке."""
        return 1.0 if self.born is None else ease((time.monotonic() - self.born) / INTRO)

    def run(self, draw, tick=None):
        threading.Thread(target=self.reader, daemon=True).start()
        last = 0.0
        while True:
            now = time.monotonic()
            if tick:
                tick(self, now)
            with self.lock:
                ok = self.size and self.size[0] > 0 and self.size[1] > 0
                animating = now < self.anim_until
                due = self.dirty or animating or now - last >= HEARTBEAT
                if ok and due:
                    self.dirty = False
                    size, theme, opts = self.size, dict(self.theme), dict(self.opts)
            if ok and due:
                emit(size[0], size[1], lambda c, w, h: draw(self, c, w, h, theme, opts, now))
                last = now
            time.sleep(1 / INTRO_FPS if animating else 0.05)
