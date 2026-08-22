"""
Giriş akışı + UYAP izleme (auto-watch):
  - Mesai saati zamanlaması
  - Takılı e-imza kartı tespiti; kart yoksa mobil imza fallback
  - E-imza 3 kez başarısız olursa mobil imza fallback
  - Durum callback'i (renkli gösterge) ve masaüstü bildirimleri
"""
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime

from .browser import UyapBrowser
from . import pin_handler
from . import card as card_mod
from . import notifier
from . import report


# ---------------- tek yöntemle giriş ----------------
def _do_method(browser, config, method, pin, logger, stop_flag):
    """Portalı açar ve verilen yöntemle (eimza/mobil/imzaco) tek deneme yapar."""
    if method == "imzaco":
        if not browser.do_imzaco():
            return False
        if not browser.wait_login_complete():
            return False
        # imza.co paneli UYAP'a ulaşamıyorsa hata modali birkaç sn gecikmeli
        # çıkabiliyor; kısa bekleyip sayfada hata var mı doğrula.
        time.sleep(6)
        err = browser.session_error_text()
        if err:
            logger.warning("imza.co girişi sonrası UYAP bağlantı hatası: %s", err[:150])
            return False
        return True
    browser.open_portal()
    if method == "mobil":
        if not browser.do_mobil_imza():
            return False
    else:
        if not browser.click_eimza_and_open_modal(max_attempts=4, wait_after_click=6):
            # Modal hiç açılmadı; yine de PIN doldurma fonksiyonunu ver
            # (belki gecikmeli açılır)
            logger.warning("Butona tıklandı ama PIN modal görünmedi; "
                           "yine de PIN doldurma denenecek.")
        if config.get("auto_type_pin", True):
            # 1) UYAP HTML PIN modal'ını doldurmayı dene (yeni UYAP sürümü)
            time.sleep(1.0)
            filled = False
            try:
                filled = browser.fill_uyap_pin_modal(pin, timeout=30)
            except Exception as exc:
                logger.warning("UYAP PIN modal doldurma hata: %s", exc)
            # 2) HTML modal bulunmadıysa Windows native pencere için thread
            if not filled:
                logger.info("HTML modal doldurulmadı; Windows PIN penceresi "
                            "yaklaşımına düşülüyor.")
                pin_stop = {"stop": False}
                t = threading.Thread(
                    target=pin_handler.wait_and_fill_pin,
                    args=(pin, config, logger, pin_stop),
                    daemon=True,
                )
                t.start()
        else:
            logger.info("PIN penceresi açıldığında PIN'i elle giriniz.")
    ok = browser.wait_login_complete()
    return ok


def login_with_fallback(browser, config, pin, logger, stop_flag, emit=None):
    """
    Giriş öncelik zinciri (sabit sıra):
      1) imza.co (bilgiler kayıtlıysa)
      2) E-imza / akıllı kart (varsayılan 2 deneme)
      3) Mobil imza
    Hepsi başarısız olursa False döner; izleme modu 30 dk bekleyip
    zinciri aynı sırayla yeniden dener.
    """
    def _emit(state, msg):
        if emit:
            emit(state, msg)
        else:
            logger.info(msg)

    max_eimza = int(config.get("eimza_max_attempts", 2))
    _emit("login", "Giriş öncelik sırası: imza.co → E-imza → Mobil imza")

    # --- 1) imza.co ---
    ic = config.get("imzaco", {}) or {}
    if str(ic.get("username", "")).strip() and str(ic.get("password", "")).strip():
        if stop_flag.get("stop"):
            return False
        _emit("login", "1/3: imza.co ile giriş deneniyor...")
        try:
            if _do_method(browser, config, "imzaco", pin, logger, stop_flag):
                return True
        except Exception as exc:
            logger.warning("imza.co girişinde hata: %s", exc)
        _emit("login", "imza.co başarısız → E-imza deneniyor...")
    else:
        logger.info("imza.co bilgileri kayıtlı değil; bu adım atlanıyor.")

    # --- 2) E-imza (akıllı kart) ---
    present = card_mod.card_present(config, logger)
    if present is False:
        _emit("login", "Takılı e-imza kartı bulunamadı; E-imza adımı atlanıyor.")
    else:
        for i in range(1, max_eimza + 1):
            if stop_flag.get("stop"):
                return False
            _emit("login", "2/3: E-imza giriş denemesi %d/%d..." % (i, max_eimza))
            try:
                if _do_method(browser, config, "eimza", pin, logger, stop_flag):
                    return True
            except Exception as exc:
                logger.warning("E-imza girişinde hata: %s", exc)
            logger.warning("E-imza giriş denemesi %d başarısız.", i)
        _emit("login", "E-imza %d denemede başarısız → Mobil imza deneniyor..." % max_eimza)

    # --- 3) Mobil imza ---
    if stop_flag.get("stop"):
        return False
    _emit("login", "3/3: Mobil imza ile giriş deneniyor...")
    try:
        if _do_method(browser, config, "mobil", pin, logger, stop_flag):
            return True
    except Exception as exc:
        logger.warning("Mobil imza girişinde hata: %s", exc)
    _emit("error", "Tüm giriş yöntemleri başarısız.")
    return False


# ---------------- tek seferlik giriş ----------------
def run_login(config, pin, logger, stop_flag, on_finish=None, state_cb=None):
    browser = UyapBrowser(config, logger)

    def emit(state, msg):
        logger.info(msg)
        if state_cb:
            state_cb(state, msg)

    try:
        browser.start()
        success = login_with_fallback(browser, config, pin, logger, stop_flag, emit)
        if success:
            browser.dismiss_popups(passes=4, wait_between=2)
            browser.run_tasks(pin)
            emit("logged_in", "Giriş başarılı. Tarayıcı açık bırakıldı.")
            notifier.notify("UYAP Girişi", "UYAP'a başarıyla giriş yapıldı.",
                            config.get("notifications", True), logger)
        else:
            emit("error", "Giriş doğrulanamadı. Tarayıcıyı kontrol edin.")
        if on_finish:
            on_finish(success)
    except Exception as exc:
        logger.error("Giriş akışında hata: %s", exc)
        emit("error", "Giriş sırasında hata oluştu.")
        if on_finish:
            on_finish(False)
    finally:
        stop_flag["stop"] = True


# ---------------- yardımcılar ----------------
def site_reachable(url, timeout=10):
    try:
        req = urllib.request.Request(url, method="GET",
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 500
    except urllib.error.HTTPError as e:
        return e.code < 500
    except Exception:
        return False


def _driver_alive(browser):
    if not browser.driver:
        return False
    try:
        _ = browser.driver.current_url
        return True
    except Exception:
        return False


def _needs_login(browser, config):
    try:
        current = (browser.driver.current_url or "").lower()
    except Exception:
        return True
    not_url = config.get("success_url_not_contains", "/giris").lower()
    if not_url and not_url in current:
        return True
    try:
        err = browser.session_error_text()
        if err:
            browser.logger.warning(
                "Oturum/bağlantı hatası tespit edildi: %s — yeniden giriş yapılacak.",
                err[:150])
            return True
    except Exception:
        pass
    return False


def _scheduled_due(job, last_runs):
    """Zamanlı görev şimdi çalışmalı mı? (Gün uygun + saat geçti + bugün çalışmadıysa)"""
    now = datetime.now()
    days = job.get("days")
    if days and now.isoweekday() not in days:
        return False
    t = str(job.get("time", "")).strip()
    try:
        hh, mm = [int(x) for x in t.split(":")]
    except Exception:
        return False
    sched = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if now < sched:
        return False
    key = job.get("name") or t
    return last_runs.get(key) != now.date().isoformat()


def within_schedule(config):
    """Mesai zamanlaması açıksa şu an aralık içinde miyiz?"""
    s = config.get("schedule", {})
    if not s.get("enabled"):
        return True
    now = datetime.now()
    days = s.get("days")
    if days and now.isoweekday() not in days:
        return False
    start = s.get("start", "00:00")
    end = s.get("end", "23:59")
    cur = now.strftime("%H:%M")
    return start <= cur <= end


def _sleep_interruptible(seconds, stop_flag):
    end = time.time() + seconds
    while time.time() < end:
        if stop_flag.get("stop"):
            return
        time.sleep(0.5)


# ---------------- izleme (auto-watch) ----------------
def run_watch(config, pin, logger, stop_flag, state_cb=None):
    interval = config.get("watch_interval_seconds", 30)
    down_wait = config.get("site_down_retry_seconds", 60)
    notif_on = config.get("notifications", True)
    url = config["portal_url"]

    browser = UyapBrowser(config, logger)
    history = []
    sched_last = {}

    def emit(state, msg):
        logger.info(msg)
        history.append((datetime.now().strftime("%Y-%m-%d %H:%M:%S"), state, msg))
        if len(history) > 5000:
            del history[:2000]
        if state_cb:
            state_cb(state, msg)

    logger.info("UYAP izleme modu başladı (aralık: %s sn).", interval)
    prev_down = False
    prev_off = False
    logged_in = False

    try:
        while not stop_flag.get("stop"):
            # 1) mesai zamanlaması
            if not within_schedule(config):
                if not prev_off:
                    emit("offhours", "Mesai saatleri dışında; izleme beklemede.")
                prev_off = True
                logged_in = False
                _sleep_interruptible(interval, stop_flag)
                continue
            prev_off = False

            # 2) UYAP ayakta mı?
            if not site_reachable(url):
                if not prev_down:
                    emit("down", "UYAP erişilemiyor/düşük.")
                    notifier.notify("UYAP Erişilemiyor",
                                    "UYAP şu an yanıt vermiyor. İzleniyor...",
                                    notif_on, logger)
                prev_down = True
                logged_in = False
                _sleep_interruptible(down_wait, stop_flag)
                continue
            if prev_down:
                emit("up", "UYAP tekrar erişilebilir.")
                notifier.notify("UYAP Ayakta",
                                "UYAP tekrar erişilebilir, giriş yapılıyor.",
                                notif_on, logger)
            prev_down = False

            # 3) tarayıcı canlı mı?
            if not _driver_alive(browser):
                emit("login", "Tarayıcı başlatılıyor...")
                try:
                    browser.quit()
                    browser.start()
                    logged_in = False
                except Exception as exc:
                    logger.error("Tarayıcı başlatılamadı: %s", exc)
                    _sleep_interruptible(interval, stop_flag)
                    continue

            # 4) giriş gerekli mi?
            if not logged_in or _needs_login(browser, config):
                ok = login_with_fallback(browser, config, pin, logger, stop_flag, emit)
                if ok:
                    logged_in = True
                    browser.dismiss_popups(passes=4, wait_between=2)
                    browser.run_tasks(pin)
                    emit("logged_in", "Giriş başarılı. Oturum izleniyor.")
                    notifier.notify("UYAP Girişi",
                                    "UYAP'a otomatik giriş yapıldı.",
                                    notif_on, logger)
                else:
                    logged_in = False
                    retry_wait = int(config.get("chain_retry_wait_seconds", 1800))
                    emit("error",
                         "Tüm giriş yöntemleri başarısız; %d dk sonra aynı sırayla "
                         "tekrar denenecek." % max(1, retry_wait // 60))
                    _sleep_interruptible(retry_wait, stop_flag)
                    continue
            else:
                try:
                    browser.dismiss_popups()
                except Exception:
                    pass
                emit("logged_in", "Oturum aktif.")

            # 5) zamanlı görevler (belirli saatte dosya sorgu/rapor)
            if logged_in:
                for job in config.get("scheduled_tasks", []):
                    if stop_flag.get("stop"):
                        break
                    if not _scheduled_due(job, sched_last):
                        continue
                    name = job.get("name") or job.get("time", "gorev")
                    emit("login", "Zamanlı görev çalışıyor: %s" % name)
                    try:
                        tasks = job.get("tasks", [])
                        if tasks:
                            browser.run_task_list(tasks, pin)
                        if job.get("export_report"):
                            path = report.resolve_report_path(job.get("report_path", ""))
                            report.write_report(path, history)
                            emit("logged_in", "Rapor üretildi: %s" % path)
                            notifier.notify("UYAP Rapor",
                                            "Zamanlı rapor üretildi: %s" % path,
                                            notif_on, logger)
                        emit("logged_in", "Zamanlı görev tamam: %s" % name)
                    except Exception as exc:
                        logger.error("Zamanlı görev hatası (%s): %s", name, exc)
                    finally:
                        sched_last[name] = datetime.now().date().isoformat()

            _sleep_interruptible(interval, stop_flag)
    finally:
        emit("idle", "İzleme modu durdu.")
