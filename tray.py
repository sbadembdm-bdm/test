"""Sistem tepsisi (system tray) simgesi. pystray/Pillow yoksa sessizce devre dışı."""

try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except Exception:
    HAS_TRAY = False


def _make_image(color="#24377f"):
    try:
        from .config import assets_dir
        p = assets_dir() / "icon.png"
        if p.exists():
            base = Image.open(p).convert("RGBA").resize((64, 64))
            d = ImageDraw.Draw(base)
            d.ellipse((42, 42, 62, 62), fill=color, outline="white", width=2)
            return base
    except Exception:
        pass
    img = Image.new("RGB", (64, 64), color)
    d = ImageDraw.Draw(img)
    d.ellipse((14, 14, 50, 50), fill="white")
    d.ellipse((24, 24, 40, 40), fill=color)
    return img


class Tray:
    """
    Basit tray sarmalayıcı. Tüm callback'ler tray thread'inde çağrılır;
    GUI tarafında root.after ile ana thread'e taşınmalıdır.
    """

    STATUS_COLORS = {
        "up": "#1a7f37",
        "logged_in": "#1a7f37",
        "login": "#b26a00",
        "down": "#b42318",
        "error": "#b42318",
        "offhours": "#555555",
        "idle": "#24377f",
    }

    def __init__(self, on_show, on_start, on_stop, on_quit):
        self.on_show = on_show
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_quit = on_quit
        self.icon = None

    def start(self):
        if not HAS_TRAY:
            return False
        menu = pystray.Menu(
            pystray.MenuItem("Göster", lambda: self.on_show()),
            pystray.MenuItem("İzlemeyi Başlat", lambda: self.on_start()),
            pystray.MenuItem("Durdur", lambda: self.on_stop()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Çıkış", lambda: self._quit()),
        )
        try:
            self.icon = pystray.Icon("bdm-uyap-giris", _make_image(),
                                     "BDM UYAP GİRİŞ", menu)
            self.icon.run_detached()
            return True
        except Exception:
            self.icon = None
            return False

    def set_status(self, state, text=""):
        if not self.icon:
            return
        color = self.STATUS_COLORS.get(state, "#24377f")
        try:
            self.icon.icon = _make_image(color)
            self.icon.title = ("BDM UYAP GİRİŞ — %s" % text) if text else "BDM UYAP GİRİŞ"
        except Exception:
            pass

    def notify(self, title, msg):
        if self.icon:
            try:
                self.icon.notify(msg, title)
            except Exception:
                pass

    def _quit(self):
        try:
            self.on_quit()
        finally:
            self.stop()

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None
