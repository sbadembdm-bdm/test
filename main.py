"""
BDM UYAP GİRİŞ - Başlangıç noktası.

Kullanım:
    python main.py            -> Arayüzü (GUI) açar
    python main.py --cli      -> Arayüzsüz tek seferlik giriş (terminal)
    python main.py --watch    -> Arayüzsüz izleme modu (PIN'i keyring'den alır)
"""
import argparse
import sys

if sys.platform.startswith("win"):
    # DPI farkındalığı: Windows ekran ölçeklendirmesi (%125, %150 vb.) açıkken
    # fare koordinatlarının doğru hesaplanması için şart.
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

from uyap_login.config import load_config
from uyap_login.logger import get_logger

KEYRING_SERVICE = "bdm-uyap-giris"
KEYRING_USER = "smartcard-pin"


def _pin_from_keyring(profile="Varsayılan"):
    try:
        import keyring
        return keyring.get_password(KEYRING_SERVICE, "pin::%s" % profile) or ""
    except Exception:
        return ""


def run_cli():
    from getpass import getpass
    from uyap_login import runner
    from uyap_login.config import resolve

    cfg = load_config()
    flat = resolve(cfg)
    logger = get_logger()
    pin = ""
    if flat.get("login_method", "eimza") == "eimza" and flat.get("auto_type_pin", True):
        pin = getpass("Akıllı kart PIN: ")

    stop_flag = {"stop": False}
    if flat.get("auto_watch"):
        runner.run_watch(flat, pin, logger, stop_flag)
    else:
        runner.run_login(flat, pin, logger, stop_flag)
        input("Bitti. Kapatmak için Enter'a basın...")


def run_watch_cli():
    """Arayüzsüz izleme (Windows başlangıcı için). PIN keyring'den alınır."""
    from uyap_login import runner
    from uyap_login.config import resolve
    cfg = load_config()
    flat = resolve(cfg)
    logger = get_logger()
    pin = _pin_from_keyring(flat.get("_profile_name", "Varsayılan"))
    if not pin and flat.get("auto_type_pin", True):
        logger.warning("Keyring'de PIN yok. PIN penceresini elle girmeniz gerekebilir.")
    stop_flag = {"stop": False}
    runner.run_watch(flat, pin, logger, stop_flag)


def main():
    parser = argparse.ArgumentParser(description="BDM UYAP GİRİŞ")
    parser.add_argument("--cli", action="store_true", help="Arayüzsüz tek giriş")
    parser.add_argument("--watch", action="store_true", help="Arayüzsüz izleme modu")
    args = parser.parse_args()

    if args.watch:
        run_watch_cli()
    elif args.cli:
        run_cli()
    else:
        try:
            from uyap_login.gui import main as gui_main
            gui_main()
        except Exception as exc:
            import traceback
            from pathlib import Path
            detail = traceback.format_exc()
            try:
                base = (Path(sys.executable).resolve().parent
                        if getattr(sys, "frozen", False)
                        else Path(__file__).resolve().parent)
                (base / "crash_log.txt").write_text(detail, encoding="utf-8")
            except Exception:
                pass
            try:
                import tkinter as tk
                from tkinter import messagebox
                r = tk.Tk()
                r.withdraw()
                messagebox.showerror(
                    "BDM UYAP GİRİŞ - Hata",
                    "Program başlatılamadı:\n\n%s\n\nAyrıntılar exe'nin yanındaki "
                    "crash_log.txt dosyasına yazıldı." % exc)
            except Exception:
                print(f"Arayüz başlatılamadı ({exc}). --cli ile deneyin.", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
