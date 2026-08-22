"""
Windows üzerinde açılan e-imza / akıllı kart PIN penceresini otomatik doldurur.

Not: Adalet E-İmza uygulamasının PIN ekranı işletim sistemi seviyesinde açılır,
Selenium bunu göremez. Bu yüzden pywinauto ile pencere yakalanıp PIN yazılır.

GÜVENLİK: Bazı kart okuyucular donanımsal (secure) PIN pad kullanır; bu durumda
PIN yalnızca cihaz üzerinden girilebilir ve otomatik yazma çalışmaz. O durumda
PIN'i elle girmeniz gerekir.
"""
import sys
import time

IS_WINDOWS = sys.platform.startswith("win")

if IS_WINDOWS:
    from pywinauto import Desktop
    from pywinauto.keyboard import send_keys


# Bulunma olasılığı yüksek pencere başlıkları (küçük harfle karşılaştırılıyor).
# Adalet E-İmza / AKİS / Kart Sürücüleri gibi olası tüm varyantlar.
DEFAULT_PIN_TITLES = [
    "adalet e-imza", "adalet e-i̇mza", "adalet",
    "pin", "parola", "şifre", "sifre", "password",
    "kart şifresi", "kart sifresi", "sertifika", "sertifika şifresi",
    "akıllı kart", "akilli kart", "smart card",
    "akis", "aki̇s",
    "e-imza", "e-i̇mza", "elektronik imza",
    "safenet", "gemalto", "safesign", "kartsim",
    "java", "security", "güvenlik",
]

# PIN alanı olması muhtemel Automation ID/Name değerleri
CANDIDATE_EDIT_NAMES = [
    "pin", "parola", "şifre", "sifre", "password",
    "kart şifresi", "kart sifresi",
]


def _list_visible_titles(backend="uia", limit=40):
    try:
        wins = Desktop(backend=backend).windows()
    except Exception:
        return []
    out = []
    for w in wins:
        try:
            t = w.window_text()
            if t and t.strip():
                out.append(t.strip())
        except Exception:
            pass
        if len(out) >= limit:
            break
    return out


def _title_matches(title, needles):
    t = (title or "").lower()
    for n in needles:
        if n and n.lower() in t:
            return True
    return False


def _find_pin_window(titles, logger, backend="uia"):
    """Verilen başlık listesindeki ilk eşleşen pencereyi döndürür."""
    try:
        windows = Desktop(backend=backend).windows()
    except Exception as exc:
        logger.warning("PIN taraması (%s) hata: %s", backend, exc)
        return None
    for win in windows:
        try:
            title = win.window_text() or ""
        except Exception:
            continue
        if not title.strip():
            continue
        if _title_matches(title, titles):
            logger.info("PIN penceresi bulundu (%s): '%s'", backend, title)
            return win
    return None


def _find_edit_and_type(win, pin, logger):
    """Pencere içinde PIN yazılabilecek Edit alanını bulup PIN'i yazar."""
    # 1) Automation ID / Name üzerinden dene
    for name in CANDIDATE_EDIT_NAMES:
        try:
            field = win.child_window(title_re="(?i).*" + name + ".*",
                                     control_type="Edit")
            if field.exists(timeout=0.5):
                try:
                    field.set_focus()
                except Exception:
                    pass
                field.type_keys(pin, with_spaces=False, set_foreground=True)
                logger.info("PIN yazıldı (Edit adı: %s).", name)
                return True
        except Exception:
            continue

    # 2) Pencere içindeki tüm Edit alanlarını tara, boş/tek olan doldurulur
    try:
        edits = win.descendants(control_type="Edit")
    except Exception:
        edits = []
    edits = [e for e in edits if _edit_visible(e)]
    if edits:
        target = edits[0]
        try:
            target.set_focus()
        except Exception:
            pass
        try:
            target.type_keys(pin, with_spaces=False, set_foreground=True)
            logger.info("PIN yazıldı (ilk görünür Edit alanı).")
            return True
        except Exception as exc:
            logger.warning("Edit alanına yazılamadı: %s. Klavye ile denenecek.", exc)

    # 3) Son çare: pencereyi odakla, düz klavye ile yaz
    try:
        win.set_focus()
        time.sleep(0.3)
        send_keys(pin, with_spaces=False, pause=0.04)
        logger.info("PIN yazıldı (klavye emülasyonu).")
        return True
    except Exception as exc:
        logger.error("PIN yazılamadı: %s", exc)
        return False


def _edit_visible(elem):
    try:
        return elem.is_visible() and elem.is_enabled()
    except Exception:
        return True


def _press_ok(win, logger):
    """Pencerede OK/Tamam benzeri butona bas; yoksa Enter gönder."""
    ok_names = ["tamam", "ok", "onayla", "giriş", "giris", "devam", "kabul"]
    try:
        buttons = win.descendants(control_type="Button")
    except Exception:
        buttons = []
    for btn in buttons:
        try:
            txt = (btn.window_text() or "").strip().lower()
        except Exception:
            continue
        if any(n in txt for n in ok_names) and "iptal" not in txt and "vazgeç" not in txt:
            try:
                btn.click_input()
                logger.info("Onay butonuna tıklandı: '%s'", btn.window_text())
                return True
            except Exception:
                pass
    try:
        send_keys("{ENTER}")
        return True
    except Exception:
        return False


def _try_click_chrome_open_dialog(logger):
    """Chrome'un 'X sitesi <protocol>:// açmak istiyor. Aç?' onay diyalogunu
    YALNIZCA UYAP/Adalet E-İmza sekmesindeyken yakalar. Yanlışlıkla başka
    sitelerin (Emergent Support gibi) protokol diyaloglarına dokunmasın diye
    pencere BAŞLIĞINDA 'uyap' veya 'adalet' geçmesi ŞART."""
    if not IS_WINDOWS:
        return False
    open_button_names = ("aç", "ac", "open")
    try:
        wins = Desktop(backend="uia").windows()
    except Exception:
        return False
    for w in wins:
        try:
            title = (w.window_text() or "").lower()
        except Exception:
            continue
        if "chrome" not in title:
            continue
        # Yalnızca UYAP / Adalet E-İmza sekmesindeki Chrome penceresi
        if not any(k in title for k in ("uyap", "adalet", "avukat portal")):
            continue
        try:
            buttons = w.descendants(control_type="Button")
        except Exception:
            continue
        for btn in buttons:
            try:
                name = (btn.window_text() or "").strip().lower()
            except Exception:
                continue
            if not name:
                continue
            if name in open_button_names or name.startswith("aç"):
                try:
                    btn.click_input()
                    logger.info("Chrome protokol onay diyalogu tıklandı: '%s'",
                                btn.window_text())
                    return True
                except Exception:
                    continue
    return False


def wait_and_fill_pin(pin, config, logger, stop_flag):
    """
    PIN penceresini bekler ve bulur bulmaz PIN'i yazıp Enter'a basar.
    stop_flag: {"stop": bool} yapısında; True olunca beklemeyi bırakır.
    """
    if not IS_WINDOWS:
        logger.warning("Otomatik PIN girişi yalnızca Windows'ta çalışır. "
                       "PIN'i elle giriniz.")
        return False

    if not pin:
        logger.info("PIN girilmemiş; pencere açıldığında elle giriniz.")
        return False

    titles = list(config.get("pin_window_titles", []) or [])
    titles.extend(DEFAULT_PIN_TITLES)
    timeout = config.get("timeouts", {}).get("pin_window_wait", 60)
    debug_titles = bool(config.get("debug_pin_windows", True))
    deadline = time.time() + timeout

    logger.info("PIN penceresi bekleniyor (%s sn)...", timeout)
    last_seen_dump = 0
    chrome_dialog_tried = False
    while time.time() < deadline:
        if stop_flag.get("stop"):
            return False

        # 0) Chrome "adalet-eimza://" harici uygulama onay diyalogunu yakala
        if not chrome_dialog_tried:
            if _try_click_chrome_open_dialog(logger):
                chrome_dialog_tried = True
                time.sleep(1.5)

        # Önce UIA backend, sonra Win32 backend
        win = _find_pin_window(titles, logger, backend="uia")
        if win is None:
            win = _find_pin_window(titles, logger, backend="win32")

        if win is not None:
            try:
                try:
                    win.set_focus()
                except Exception:
                    pass
                time.sleep(0.5)
                # Kullanıcı config'ten sabit Automation ID vermişse önce onu dene
                auto_id = config.get("pin_field_automation_id", "")
                if auto_id:
                    try:
                        field = win.child_window(auto_id=auto_id, control_type="Edit")
                        field.set_focus()
                        field.type_keys(pin, with_spaces=False)
                        time.sleep(0.3)
                        _press_ok(win, logger)
                        logger.info("PIN otomatik girildi ve onaylandı.")
                        return True
                    except Exception as exc:
                        logger.warning("Sabit auto_id (%s) çalışmadı: %s. "
                                       "Otomatik alan araması yapılacak.",
                                       auto_id, exc)

                if _find_edit_and_type(win, pin, logger):
                    time.sleep(0.3)
                    _press_ok(win, logger)
                    logger.info("PIN otomatik girildi ve onaylandı.")
                    return True
                logger.warning("PIN alanına yazılamadı. Elle giriniz.")
                return False
            except Exception as exc:
                logger.error("PIN yazılırken hata: %s. Elle giriniz.", exc)
                return False

        # Debug: her 5 saniyede bir görünen pencereleri logla
        now = time.time()
        if debug_titles and now - last_seen_dump >= 5:
            last_seen_dump = now
            visible = _list_visible_titles("uia")
            if visible:
                short = ", ".join(t[:60] for t in visible[:12])
                logger.info("Açık pencereler (PIN aranıyor): %s", short)
        time.sleep(1)

    logger.warning("PIN penceresi zaman aşımına uğradı. Elle giriniz.")
    return False
