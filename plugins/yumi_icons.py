"""Поиск цветной иконки приложения так же, как её находит меню приложений (16.10.2026, тачбар yumi-boot).

Тема — из gtk-3.0/settings.ini (сейчас Yumi-Folders), дальше по её Inherits= (Tela-circle-dracula, breeze-dark,
hicolor). Каталоги: ~/.local/share/icons, /usr/share/icons, экспорт flatpak, /usr/share/pixmaps. Берётся самый
крупный подходящий размер; SVG рисуется через librsvg, PNG — через cairo. Результат кэшируется.
"""
import configparser, glob, os
import cairo

HOME = os.path.expanduser("~")
BASES = [f"{HOME}/.local/share/icons", f"{HOME}/.icons", f"{HOME}/.local/share/flatpak/exports/share/icons",
         "/var/lib/flatpak/exports/share/icons", "/usr/share/icons"]
_cache = {}


def _theme():
    p = configparser.ConfigParser()
    try:
        p.read(f"{HOME}/.config/gtk-3.0/settings.ini")
        return p.get("Settings", "gtk-icon-theme-name", fallback="hicolor")
    except configparser.Error:
        return "hicolor"


def _chain():
    seen, order, todo = set(), [], [_theme()]
    while todo:
        t = todo.pop(0)
        if t in seen:
            continue
        seen.add(t); order.append(t)
        for b in BASES:
            idx = f"{b}/{t}/index.theme"
            if os.path.exists(idx):
                p = configparser.ConfigParser(interpolation=None, strict=False)
                try:
                    p.read(idx)
                    todo += [x.strip() for x in p.get("Icon Theme", "Inherits", fallback="").split(",") if x.strip()]
                except configparser.Error:
                    pass
                break
    if "hicolor" not in order:
        order.append("hicolor")
    return order


def _size_of(path):
    for part in path.split("/"):
        if part in ("scalable", "symbolic"):
            return 10000 if part == "scalable" else -1
        n = part.split("@")[0].split("x")[0]
        if n.isdigit():
            return int(n)
    return 0


def find(name):
    """Путь к файлу иконки (лучший размер) или None."""
    if os.path.isabs(name):
        return name if os.path.exists(name) else None
    for t in _chain():
        cand = []
        for b in BASES:
            cand += [f for f in glob.glob(f"{b}/{t}/**/{name}.*", recursive=True)
                     if f.endswith((".svg", ".png")) and "symbolic" not in f and "/actions/" not in f]
        if cand:
            return max(cand, key=_size_of)
    for f in (f"/usr/share/pixmaps/{name}.svg", f"/usr/share/pixmaps/{name}.png"):
        if os.path.exists(f):
            return f
    return None


CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME", f"{HOME}/.cache"), "yumi-touchbar-icons")


def surface(name, px):
    """cairo.ImageSurface px×px с иконкой (или None). Готовые картинки — в ~/.cache/yumi-touchbar-icons
    (агент перезапускает плагин при каждом показе слоя: поиск по теме + SVG ≈ 1 с, из кэша — миллисекунды)."""
    key = (name, px)
    if key in _cache:
        return _cache[key]
    cpng = os.path.join(CACHE, f"{name.replace('/', '_')}-{px}.png")
    if os.path.exists(cpng):
        try:
            _cache[key] = cairo.ImageSurface.create_from_png(cpng)
            return _cache[key]
        except Exception:
            pass
    path, s = find(name), None
    if path:
        try:
            s = cairo.ImageSurface(cairo.FORMAT_ARGB32, px, px)
            c = cairo.Context(s)
            if path.endswith(".svg"):
                import gi
                gi.require_version("Rsvg", "2.0")
                from gi.repository import Rsvg
                h = Rsvg.Handle.new_from_file(path)
                r = Rsvg.Rectangle(); r.x, r.y, r.width, r.height = 0, 0, px, px
                h.render_document(c, r)
            else:
                img = cairo.ImageSurface.create_from_png(path)
                k = px / max(img.get_width(), img.get_height())
                c.scale(k, k); c.set_source_surface(img, 0, 0)
                c.get_source().set_filter(cairo.FILTER_GOOD); c.paint()
            s.flush()
        except Exception:
            s = None
    if s is not None:
        try:
            os.makedirs(CACHE, exist_ok=True)
            s.write_to_png(cpng + ".tmp"); os.replace(cpng + ".tmp", cpng)
        except OSError:
            pass
    _cache[key] = s
    return s
