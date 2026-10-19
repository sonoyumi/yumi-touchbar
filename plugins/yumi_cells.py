"""Общее для плагинов-ячеек тачбара yumi (19.10.2026): yumi-ram, yumi-airpods, yumi-output, yumi-clip, yumi-pomodoro, yumi-timer.

Тот же вид, что у yumi-status: ячейка цвета surface со скруглением 9 px, значок Nerd Font + подпись,
включённое — акцентом, касание — короткая вспышка акцентом. Рисование — cairo, цикл и протокол — yumi_glow_lib.Host.
"""
import os, subprocess, time
import cairo
from yumi_glow_lib import rgb, mix, rounded, R, M, pill, face

FLASH = 0.35


class Pal:
    """Цвета темы touchbard (тема пишется из обоев yumi-touchbar-theme)."""

    def __init__(self, theme):
        self.accent = rgb(theme.get("accent"), "#f2a07b")
        self.fg = rgb(theme.get("fg"), "#f3ece7")
        self.surface = rgb(theme.get("surface"), "#16242a")
        self.dim = rgb(theme.get("fg_dim"), "#8c9ca6")
        self.red = rgb(theme.get("red"), "#ed8796")
        self.yellow = rgb(theme.get("yellow"), "#eed49f")
        self.font = theme.get("font") or "JetBrainsMono Nerd Font"
        self.theme = theme


def spawn(cmd):
    """Команда в фоне, как бинд Hyprland (своя сессия — не умрёт вместе с плагином)."""
    subprocess.Popen(["sh", "-c", cmd], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run(*cmd, timeout=3):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def cell(c, x, w, h, pal, k, flash_at=-9.0, now=None, fill=None):
    """Фон ячейки [x, x+w) с полями как у кнопок; flash_at — время касания (вспышка FLASH секунд)."""
    now = time.monotonic() if now is None else now
    f = max(0.0, 1 - (now - flash_at) / FLASH)
    pill(c, x + 3, M, w - 6, h - 2 * M, pal.theme, mix(fill or pal.surface, pal.accent, .45 * f), k)


def text_w(c, pal, s, px, bold=True):
    """Ширина текста: шаг пера или реальная ширина рисунка — что больше (значки Nerd Font шире своего шага)."""
    face(c, pal.theme, s, px, bold)
    e = c.text_extents(s)
    return max(e.x_advance, e.x_bearing + e.width)


def fit(c, pal, s, px, room, bold=True):
    """Обрезать подпись «…», чтобы влезла в room пикселей."""
    while s and text_w(c, pal, s, px, bold) > room and len(s) > 2:
        s = s[:-2] + "…"
    return s


def text(c, pal, s, px, x, h, ink, k, bold=True, cy=None):
    """Текст с левым краем x, по центру строки (cy — центр по вертикали, по умолчанию середина)."""
    face(c, pal.theme, s, px, bold)
    e = c.text_extents(s)
    c.move_to(x - e.x_bearing, (h / 2 if cy is None else cy) - e.height / 2 - e.y_bearing)
    c.set_source_rgba(*ink, k)
    c.show_text(s)
    return max(e.x_advance, e.x_bearing + e.width)


def glyph(c, pal, g, px, x, h, ink, k):
    """Значок Nerd Font (обычное начертание), левый край x; возвращает ширину."""
    return text(c, pal, g, px, x, h, ink, k, bold=False)


def row(c, pal, parts, x0, w, h, k, gap=10):
    """Ряд [(текст, px, цвет, жирный, значок?)] по центру ячейки шириной w; возвращает правый край."""
    widths = [text_w(c, pal, s, px, b and not g) for s, px, _, b, g in parts]
    total = sum(widths) + gap * (len(parts) - 1)
    x = x0 + (w - total) / 2
    for (s, px, ink, b, g), wd in zip(parts, widths):
        text(c, pal, s, px, x, h, ink, k, bold=b and not g)
        x += wd + gap
    return x


def home(*p):
    return os.path.join(os.path.expanduser("~"), *p)
