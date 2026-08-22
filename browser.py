"""
Selenium ile tarayıcıyı sürüp UYAP portalına e-imza / mobil imza ile giriş yapar.

Akış (e-imza):
  1) Tarayıcı açılır, UYAP portalına gidilir.
  2) 'E-İmza ile Giriş' seçeneğine tıklanır.
  3) Arka planda çalışan 'Adalet E-İmza' uygulaması sertifika ister; PIN penceresi
     açılır (pin_handler bunu doldurur).
  4) Giriş tamamlanınca ana sayfa/başarı kontrolü yapılır.
"""
import os
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class UyapBrowser:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.driver = None

    # ---------- tarayıcı başlatma ----------
    # ---------- profil klonlama ----------
    def _list_chrome_profiles(self, real_dir):
        """Chrome 'User Data' altındaki gerçek profil klasörlerini ve
        display name'leri döndürür: [(folder, display_name, user_name)]."""
        result = []
        if not os.path.isdir(real_dir):
            return result
        try:
            import json
            ls_path = os.path.join(real_dir, "Local State")
            info_cache = {}
            if os.path.exists(ls_path):
                with open(ls_path, "r", encoding="utf-8") as f:
                    ls = json.load(f)
                info_cache = ((ls.get("profile") or {}).get("info_cache") or {})
            for name in os.listdir(real_dir):
                p = os.path.join(real_dir, name)
                if not os.path.isdir(p):
                    continue
                if name != "Default" and not name.startswith("Profile"):
                    continue
                meta = info_cache.get(name, {}) or {}
                display = (meta.get("name") or "").strip()
                user = (meta.get("user_name") or "").strip()
                result.append((name, display, user))
        except Exception:
            pass
        return result

    def _resolve_chrome_profile(self, real_dir, requested):
        """Kullanıcının yazdığı 'requested' değeri disk üzerinde profil KLASÖRÜ
        değilse (örn. e-mail veya display name yazmışsa) Local State içindeki
        info_cache üzerinden gerçek klasör adına eşler."""
        if not requested:
            return "Default"
        # 1) Doğrudan klasör mü?
        if os.path.isdir(os.path.join(real_dir, requested)):
            return requested
        # 2) info_cache üzerinden display_name / user_name eşle
        needle = requested.strip().lower()
        best = None
        for folder, display, user in self._list_chrome_profiles(real_dir):
            for cand in (display, user):
                if not cand:
                    continue
                if cand.strip().lower() == needle:
                    return folder
                if needle in cand.strip().lower():
                    best = best or folder
        if best:
            self.logger.info("Profil '%s' → '%s' olarak eşlendi.", requested, best)
            return best
        # 3) Bulamadık: mevcut profilleri log'a bas
        profiles = self._list_chrome_profiles(real_dir)
        if profiles:
            listing = ", ".join(
                "%s (%s)" % (f, d or u or "-") for f, d, u in profiles[:10])
            self.logger.warning(
                "Profil '%s' Chrome'da bulunamadı. Mevcut profiller: %s",
                requested, listing)
        else:
            self.logger.warning("Chrome profillerini okuma başarısız.")
        return None

    def _prepare_user_profile(self):
        """Chrome 136+ gerçek 'User Data' klasörünü otomasyona kapattı; profil
        (eklentiler dahil) bir kez otomasyon kopyasına klonlanır ve o kullanılır."""
        custom = (self.config.get("chrome_profile_dir") or "").strip()
        if custom and os.path.isdir(custom):
            return custom, self.config.get("chrome_profile_name") or "Default"

        real = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
        auto = os.path.expandvars(r"%LOCALAPPDATA%\BDM-UYAP-GIRIS\ChromeProfile")
        requested = self.config.get("chrome_profile_name") or "Default"
        prof = self._resolve_chrome_profile(real, requested) or "Default"
        if prof != requested:
            self.logger.info(
                "Chrome profili: '%s' bulunamadı, gerçek klasör '%s' kullanılıyor.",
                requested, prof)

        src_prof = os.path.join(real, prof)
        if not os.path.isdir(src_prof):
            self.logger.error(
                "Chrome kaynak profili yok: %s. Chrome'un yüklü olduğundan ve "
                "en az bir kez açıldığından emin olun. Uzantıları olmayan "
                "geçici profille devam edilecek.", src_prof)
            os.makedirs(os.path.join(auto, "Default"), exist_ok=True)
            self._patch_profile_prefs(os.path.join(auto, "Default"))
            return auto, "Default"

        # Klon var mı ve SAĞLIKLI mı? Extensions klasörü boşsa (önceki hatalı
        # klondan kalma) yeniden oluşturmak zorundayız — aksi halde Adalet
        # E-İmza extension yok → PIN modal açılmaz.
        auto_default = os.path.join(auto, "Default")
        needs_clone = not os.path.isdir(auto_default)
        if not needs_clone:
            ext_dir = os.path.join(auto_default, "Extensions")
            if not os.path.isdir(ext_dir) or not os.listdir(ext_dir):
                self.logger.warning(
                    "Klon profil içinde uzantılar (Extensions) yok. "
                    "Klon yeniden oluşturuluyor...")
                needs_clone = True
                try:
                    import shutil
                    shutil.rmtree(auto, ignore_errors=True)
                except Exception:
                    pass

        if needs_clone:
            self.logger.info("Chrome profiliniz otomasyon için kopyalanıyor "
                             "(sadece ilk sefer, birkaç dakika sürebilir)...")
            import shutil
            ignore = shutil.ignore_patterns(
                "*Cache*", "Cache*", "GrShaderCache", "ShaderCache", "Crashpad",
                "Crash Reports", "lockfile", "LOCK", "*.tmp", "Service Worker",
                "IndexedDB", "File System", "Media Cache", "GPUCache")
            os.makedirs(auto, exist_ok=True)
            try:
                local_state = os.path.join(real, "Local State")
                if os.path.exists(local_state):
                    shutil.copy2(local_state, os.path.join(auto, "Local State"))
                shutil.copytree(src_prof, os.path.join(auto, "Default"),
                                ignore=ignore, dirs_exist_ok=True)
                # Doğrulama: extension var mı?
                ext = os.path.join(auto, "Default", "Extensions")
                if os.path.isdir(ext) and os.listdir(ext):
                    self.logger.info(
                        "Profil kopyalandı: %s (kaynak: %s, uzantı klasörü: %d öge)",
                        auto, src_prof, len(os.listdir(ext)))
                else:
                    self.logger.warning(
                        "Profil kopyalandı ama Extensions klasörü boş. "
                        "Kaynak profilde uzantı yok mu? Kaynak: %s", src_prof)
            except Exception as exc:
                self.logger.warning(
                    "Profil kopyalanırken uyarı (devam ediliyor): %s", exc)
        # HER seferinde protokol izinlerini güncelle
        self._patch_profile_prefs(os.path.join(auto, "Default"))
        return auto, "Default"

    def _patch_profile_prefs(self, default_dir):
        """Klonlanmış Chrome profiline Adalet E-İmza ve benzeri protokoller için
        'her zaman izin ver' işaretini yazar; ayrıca autofill/password bubble'ı
        kapatır. Bu sayede UYAP butonu tıklandığında Chrome soru sormadan
        adalet-eimza:// protokolünü Adalet E-İmza uygulamasına dispatch eder."""
        try:
            import json
            prefs_path = os.path.join(default_dir, "Preferences")
            os.makedirs(default_dir, exist_ok=True)
            data = {}
            if os.path.exists(prefs_path):
                try:
                    with open(prefs_path, "r", encoding="utf-8") as f:
                        data = json.load(f) or {}
                except Exception:
                    data = {}
            ph = data.setdefault("protocol_handler", {})
            excl = ph.setdefault("excluded_schemes", {})
            # false = "her zaman izin ver" (kullanıcıya sormaz, direkt dispatch eder)
            for scheme in ("adalet-eimza", "adalet_eimza", "adalet",
                           "eimza", "e-imza", "imza"):
                excl[scheme] = False
            # Autofill / password manager: form doldurmada karışıklık yapmasınlar
            profile = data.setdefault("profile", {})
            pwd = profile.setdefault("password_manager_enabled", False)
            _ = pwd  # kayıt için, üstteki setdefault yeterli
            profile["password_manager_enabled"] = False
            creds = data.setdefault("credentials_enable_service", False)
            _ = creds
            data["credentials_enable_service"] = False
            autofill = data.setdefault("autofill", {})
            autofill["enabled"] = False
            autofill["profile_enabled"] = False
            autofill["credit_card_enabled"] = False
            with open(prefs_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            self.logger.info(
                "Chrome profili hazırlandı: adalet-eimza otomatik izin verildi, "
                "autofill/şifre yöneticisi kapatıldı.")
        except Exception as exc:
            self.logger.warning("Profil ön ayarı yazılamadı: %s", exc)

    def _cleanup_profile_locks(self, pdir):
        """Chrome klon profilinde kalan Singleton* kilit dosyalarını sil.
        Chrome başlatılırken bu dosyalar 'Session not created' hatasına yol
        açıyor (profil kilitli sanılıyor)."""
        for name in ("SingletonLock", "SingletonCookie", "SingletonSocket",
                     "lockfile"):
            for sub in ("", "Default"):
                p = os.path.join(pdir, sub, name) if sub else os.path.join(pdir, name)
                try:
                    if os.path.exists(p) or os.path.islink(p):
                        os.unlink(p)
                        self.logger.info("Profil kilidi temizlendi: %s", p)
                except Exception:
                    pass

    def _start_chrome_with_profile(self, pdir, pname, headless):
        opts = webdriver.ChromeOptions()
        self._apply_common_options(opts, headless)
        opts.add_argument(f"--user-data-dir={pdir}")
        opts.add_argument(f"--profile-directory={pname}")
        opts.add_argument("--no-first-run")
        opts.add_argument("--no-default-browser-check")
        opts.add_argument("--disable-background-networking")
        return webdriver.Chrome(options=opts)

    def _start_chrome(self, headless):
        if not self.config.get("use_existing_profile"):
            opts = webdriver.ChromeOptions()
            self._apply_common_options(opts, headless)
            return webdriver.Chrome(options=opts)
        pdir, pname = self._prepare_user_profile()
        self._cleanup_profile_locks(pdir)
        self.logger.info("Chrome profili kullanılıyor: %s (%s)", pdir, pname)
        try:
            return self._start_chrome_with_profile(pdir, pname, headless)
        except Exception as exc:
            msg = str(exc).lower()
            self.logger.warning("Kendi profille açılamadı (%s). Klon "
                                "yeniden hazırlanıyor...", type(exc).__name__)
            # Kilit dosyalarını agresif temizle, sonra dene
            self._cleanup_profile_locks(pdir)
            time.sleep(1)
            try:
                return self._start_chrome_with_profile(pdir, pname, headless)
            except Exception as exc2:
                # Klon tamamen bozulmuş olabilir — komple sil, yeniden kopyala
                self.logger.warning("İkinci deneme de başarısız (%s). Klon "
                                    "profil sıfırdan kopyalanacak...",
                                    type(exc2).__name__)
                try:
                    import shutil
                    shutil.rmtree(pdir, ignore_errors=True)
                except Exception:
                    pass
                pdir2, pname2 = self._prepare_user_profile()
                self._cleanup_profile_locks(pdir2)
                try:
                    return self._start_chrome_with_profile(pdir2, pname2, headless)
                except Exception as exc3:
                    self.logger.error(
                        "Klon profil hala açılamıyor (%s). E-İmza extension "
                        "yüklü olmayacak, PIN modal açılmayabilir. Chrome'unuzu "
                        "tamamen kapatın ve tekrar deneyin. Alternatif olarak "
                        "'use_existing_profile' ayarını kapatabilirsiniz.",
                        type(exc3).__name__)
                    opts2 = webdriver.ChromeOptions()
                    self._apply_common_options(opts2, headless)
                    return webdriver.Chrome(options=opts2)

    def start(self):
        browser = self.config.get("browser", "chrome").lower()
        headless = self.config.get("headless", False)
        self.logger.info("Tarayıcı başlatılıyor: %s", browser)

        if browser == "edge":
            opts = webdriver.EdgeOptions()
            self._apply_common_options(opts, headless)
            self.driver = webdriver.Edge(options=opts)
        else:
            self.driver = self._start_chrome(headless)

        self.driver.set_page_load_timeout(self.config.get("timeouts", {}).get("page_load", 40))
        return self.driver

    def _apply_common_options(self, opts, headless):
        if headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--start-maximized")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        # Chrome'un "automated test software" tespitini gizle: aksi halde Adalet
        # E-İmza gibi external protocol handler'lar (adalet-eimza://) tetiklenmez.
        try:
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_experimental_option("useAutomationExtension", False)
            # Şifre yöneticisi / autofill: form üstüne yazıp bozmasın.
            # protocol_handler.excluded_schemes: Chrome external protocol dialog'unu
            # bypass eder (adalet-eimza:// için "her zaman izin ver" kalıcı).
            opts.add_experimental_option("prefs", {
                "credentials_enable_service": False,
                "profile.password_manager_enabled": False,
                "autofill.profile_enabled": False,
                "autofill.credit_card_enabled": False,
                "protocol_handler.excluded_schemes.adalet-eimza": False,
                "protocol_handler.excluded_schemes.adalet_eimza": False,
                "protocol_handler.excluded_schemes.adalet": False,
                "protocol_handler.excluded_schemes.eimza": False,
                "protocol_handler.excluded_schemes.e-imza": False,
                "protocol_handler.excluded_schemes.imza": False,
                "protocol_handler.excluded_schemes.imzala": False,
                "protocol_handler.excluded_schemes.imzasec": False,
            })
        except Exception:
            pass
        opts.add_argument("--disable-save-password-bubble")
        opts.add_argument("--password-store=basic")

    def _real_click(self, el):
        """Selenium ile gerçek fare hareketi + tıklama (user gesture)."""
        try:
            from selenium.webdriver.common.action_chains import ActionChains
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", el)
            time.sleep(0.2)
            ActionChains(self.driver).move_to_element(el).pause(0.15).click().perform()
            return True
        except Exception:
            return False

    def _bring_browser_to_front(self):
        """Selenium'un açtığı Chrome penceresini Windows'ta öne getirir + odaklar.
        Bu yapılmadan OS-level fare tıklaması Chrome'a 'user gesture' olarak
        ulaşmıyor ve Adalet E-İmza extension modal'ı tetiklenmiyor."""
        import sys as _sys
        if not _sys.platform.startswith("win"):
            return False
        try:
            title = (self.driver.title or "").strip()
        except Exception:
            title = ""
        try:
            from pywinauto import Desktop
            targets = []
            for w in Desktop(backend="uia").windows():
                try:
                    t = (w.window_text() or "").lower()
                except Exception:
                    continue
                if "chrome" not in t:
                    continue
                # Öncelik: title'daki içerik chrome başlığında geçiyor mu?
                score = 0
                if title and title.lower() in t:
                    score = 3
                elif "uyap" in t or "avukat" in t or "adalet" in t:
                    score = 2
                elif "google chrome" in t:
                    score = 1
                if score:
                    targets.append((score, w))
            if not targets:
                self.logger.warning("Chrome penceresi bulunamadı (öne getirme).")
                return None
            targets.sort(key=lambda x: -x[0])
            w = targets[0][1]
            try:
                w.set_focus()
            except Exception:
                pass
            # Ekstra: SetForegroundWindow üzerinden zorla (bazı Chrome sürümlerinde
            # set_focus tam odak getirmez)
            try:
                import ctypes
                hwnd = w.handle
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                ctypes.windll.user32.BringWindowToTop(hwnd)
                ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            except Exception:
                pass
            time.sleep(0.4)
            try:
                self.logger.info("Chrome penceresi öne getirildi: %s",
                                 (w.window_text() or "")[:60])
            except Exception:
                pass
            return w
        except Exception as exc:
            self.logger.warning("Chrome penceresi öne getirilemedi: %s", exc)
            return None

    def _install_mouse_tracker(self):
        """Sayfaya güvenilir (trusted) mousemove olaylarını kaydeden dinleyici
        ekler. OS fare hareketi gerçek olduğu için sayfa bunu görür; böylece
        fiziksel koordinat <-> CSS koordinat eşlemesini kalibre edebiliyoruz."""
        self.driver.execute_script("""
            if (!window.__bdmTrk) {
                window.__bdmTrk = {n: 0, x: -1, y: -1};
                document.addEventListener('mousemove', function(e){
                    window.__bdmTrk = {n: (window.__bdmTrk.n||0)+1,
                                       x: e.clientX, y: e.clientY};
                }, true);
            }
        """)

    def _read_tracker(self):
        try:
            return self.driver.execute_script("return window.__bdmTrk || null;")
        except Exception:
            return None

    def _probe_mouse(self, mouse, px, py, prev_n, wait=0.9):
        """Fareyi (px,py) fiziksel noktasına taşır ve sayfanın gördüğü CSS
        koordinatını döndürür. Sayfa mousemove almadıysa None döner."""
        mouse.move(coords=(int(px), int(py)))
        deadline = time.time() + wait
        while time.time() < deadline:
            t = self._read_tracker()
            if t and t.get("n", 0) > prev_n:
                return t
            time.sleep(0.1)
        return None

    def _calibrated_click(self, el):
        """Kendini kalibre eden OS-level tıklama. Windows DPI ölçeklendirmesi
        veya pencere konumu yüzünden hesaplanan koordinat kaysa bile, fare
        sayfa üzerinde 2 test noktasına götürülüp sayfanın gerçekte gördüğü
        CSS koordinatı okunur; ölçek+ofset buradan hesaplanır ve butonun
        birebir doğru fiziksel koordinatına tıklanır."""
        from pywinauto import mouse
        win = self._bring_browser_to_front()
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", el)
        time.sleep(0.4)
        self._install_mouse_tracker()
        target = self.driver.execute_script("""
            var r = arguments[0].getBoundingClientRect();
            return {cx: r.left + r.width/2, cy: r.top + r.height/2,
                    w: r.width, h: r.height};
        """, el)
        if not win:
            return False
        try:
            rect = win.rectangle()
        except Exception as exc:
            self.logger.warning("Chrome pencere konumu okunamadı: %s", exc)
            return False
        # Probe 1: pencere merkezi (sayfa alanına denk gelir)
        p1x = (rect.left + rect.right) / 2
        p1y = (rect.top + rect.bottom) / 2 + 60
        t0 = self._read_tracker() or {"n": 0}
        c1 = self._probe_mouse(mouse, p1x, p1y, t0.get("n", 0))
        if not c1:
            self.logger.warning(
                "Kalibrasyon: sayfa fare hareketini görmedi (pencere kapalı/örtük olabilir).")
            return False
        # Probe 2: +120,+80 kaydır -> ölçek hesapla
        c2 = self._probe_mouse(mouse, p1x + 120, p1y + 80, c1["n"])
        if not c2 or c2["x"] == c1["x"] or c2["y"] == c1["y"]:
            scale_x = scale_y = 1.0
        else:
            scale_x = 120.0 / (c2["x"] - c1["x"])
            scale_y = 80.0 / (c2["y"] - c1["y"])
        base = c2 or c1
        base_px, base_py = (p1x + 120, p1y + 80) if c2 else (p1x, p1y)
        tx = base_px + (target["cx"] - base["x"]) * scale_x
        ty = base_py + (target["cy"] - base["y"]) * scale_y
        self.logger.info(
            "Kalibrasyon: ölçek=(%.2f, %.2f), hedef fiziksel=(%d, %d)",
            scale_x, scale_y, tx, ty)
        # Hedefe git ve imlecin GERÇEKTEN butonun üstünde olduğunu doğrula
        prev_n = base["n"]
        for attempt in range(3):
            cur = self._probe_mouse(mouse, tx, ty, prev_n)
            if not cur:
                self.logger.warning("Kalibrasyon: hedef nokta sayfa dışında kaldı.")
                return False
            prev_n = cur["n"]
            hit = self.driver.execute_script("""
                var e = document.elementFromPoint(arguments[1], arguments[2]);
                return !!(e && (arguments[0].contains(e) || e.contains(arguments[0])));
            """, el, cur["x"], cur["y"])
            if hit:
                self.logger.info(
                    "İmleç buton üzerinde doğrulandı (%d, %d) — tıklanıyor.",
                    tx, ty)
                mouse.click(button="left", coords=(int(tx), int(ty)))
                return True
            # Sapma varsa düzelt ve tekrar dene
            tx += (target["cx"] - cur["x"]) * scale_x
            ty += (target["cy"] - cur["y"]) * scale_y
            self.logger.info(
                "Kalibrasyon düzeltmesi %d: imleç (%.0f, %.0f) CSS'de, hedef (%.0f, %.0f); yeni fiziksel=(%d, %d)",
                attempt + 1, cur["x"], cur["y"], target["cx"], target["cy"], tx, ty)
        self.logger.warning("Kalibrasyon: imleç butonun üstüne getirilemedi.")
        return False

    def _os_level_click(self, el):
        """OS-level (Windows) gerçek fare tıklaması. Chrome external protocol
        handler (adalet-eimza://) synthesized event'leri sessizce reddettiğinde
        tek işleyen yol budur. Element'in ekran koordinatı hesaplanıp
        pywinauto.mouse.click() ile fiziksel event gönderilir. Chrome
        arka plandaysa 'user gesture' geçerli sayılmadığı için önce Chrome
        penceresini öne getiriyoruz."""
        import sys as _sys
        if not _sys.platform.startswith("win"):
            return False
        # 1) Kendini kalibre eden tıklama (DPI/pencere konumu ne olursa olsun
        #    imlecin butonun üstünde olduğu DOĞRULANARAK tıklanır)
        try:
            if self._calibrated_click(el):
                return True
            self.logger.info("Kalibre tıklama başarısız; klasik koordinat hesabına geçiliyor...")
        except Exception as exc:
            self.logger.warning("Kalibre tıklama hatası: %s", exc)
        try:
            # Chrome'u öne getir — kritik: aksi halde extension modal açılmaz
            self._bring_browser_to_front()
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", el)
            time.sleep(0.4)
            info = self.driver.execute_script("""
                var r = arguments[0].getBoundingClientRect();
                return {
                    cx: r.left + r.width/2,
                    cy: r.top + r.height/2,
                    sx: window.screenX || window.screenLeft || 0,
                    sy: window.screenY || window.screenTop || 0,
                    ow: window.outerWidth, iw: window.innerWidth,
                    oh: window.outerHeight, ih: window.innerHeight,
                    dpr: window.devicePixelRatio || 1
                };
            """, el)
            # Chrome pencere üstündeki çerçeve + adres çubuğu offset
            dpr = float(info.get("dpr") or 1)
            side = max(0, (info["ow"] - info["iw"]) / 2)
            top = max(0, info["oh"] - info["ih"] - side)
            screen_x = int((info["sx"] + side + info["cx"]) * dpr)
            screen_y = int((info["sy"] + top + info["cy"]) * dpr)
            self.logger.info("OS-level fare tıklaması (dpr=%.2f): (%d, %d)",
                             dpr, screen_x, screen_y)
            from pywinauto import mouse
            mouse.move(coords=(screen_x, screen_y))
            time.sleep(0.15)
            mouse.click(button="left", coords=(screen_x, screen_y))
            return True
        except Exception as exc:
            self.logger.warning("OS-level fare tıklaması hatası: %s", exc)
            return False

    # ---------- giriş akışı ----------
    def open_portal(self):
        url = self.config["portal_url"]
        self.logger.info("Portal açılıyor: %s", url)
        self.driver.get(url)
        try:
            WebDriverWait(self.driver, 20).until(
                lambda d: d.execute_script("return document.readyState") == "complete")
        except Exception:
            pass
        # Adalet E-İmza Chrome extension'ının content_script'inin butona
        # olay dinleyici bağlaması için ekstra bekleme; aksi halde ilk
        # tıklama boşa gider (modal açılmaz).
        warmup = int(self.config.get("extension_warmup_seconds", 10))
        if warmup > 0:
            self.logger.info("Extension hazırlanması bekleniyor (%s sn)...", warmup)
            time.sleep(warmup)
        time.sleep(1.5)

    def _js_click(self, el):
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'}); arguments[0].click();", el)

    def _find_first(self, selectors, timeout):
        for sel in selectors:
            by = By.XPATH if sel.strip().startswith("//") else By.CSS_SELECTOR
            try:
                el = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((by, sel)))
                return el, sel
            except TimeoutException:
                continue
        return None, None

    def _modal_present(self):
        """PIN modal'ının DOM'da görünür şekilde açık olup olmadığını hızlı
        kontrol eder (bekleme yok)."""
        try:
            self.driver.switch_to.default_content()
        except Exception:
            pass
        selectors = self.config.get("uyap_pin_input_selectors") or [
            "//input[@placeholder='Pin Kodu']",
            "//input[contains(@placeholder,'Pin') and @type='password']",
        ]
        for sel in selectors:
            try:
                by = By.XPATH if sel.strip().startswith("//") else By.CSS_SELECTOR
                el = self.driver.find_element(by, sel)
                if el.is_displayed():
                    return True
            except Exception:
                continue
        return False

    def click_eimza_and_open_modal(self, max_attempts=4, wait_after_click=5):
        """E-İmza butonuna tıklar ve PIN modal'ının açılmasını bekler; modal
        açılmadıysa tıklamayı tekrarlar. Fresh clone'da Adalet E-İmza extension
        henüz hazır olmadığı için ilk tıklama boşa gidebilir."""
        for attempt in range(1, max_attempts + 1):
            if attempt > 1:
                self.logger.info(
                    "PIN modal açılmadı; butona yeniden tıklanıyor (deneme %d/%d)...",
                    attempt, max_attempts)
            if not self.click_eimza_login():
                return False
            deadline = time.time() + wait_after_click
            while time.time() < deadline:
                if self._modal_present():
                    self.logger.info(
                        "PIN modal DOM'da tespit edildi (deneme %d).", attempt)
                    return True
                time.sleep(0.5)
        self.logger.warning(
            "PIN modal %d denemeye rağmen açılmadı.", max_attempts)
        return False

    def click_eimza_login(self):
        wait = self.config.get("timeouts", {}).get("element_wait", 30)
        selectors = self.config.get("eimza_button_selectors", [])
        self.logger.info("E-İmza giriş butonu aranıyor...")
        for sel in selectors:
            by = By.XPATH if sel.strip().startswith("//") else By.CSS_SELECTOR
            try:
                el = WebDriverWait(self.driver, wait).until(
                    EC.element_to_be_clickable((by, sel))
                )
                # Adalet E-İmza custom protocol'i "user gesture" gerektiriyor;
                # Chrome son sürümleri Selenium'un synthesized click'ini reddediyor.
                # 1) OS-level fiziksel fare tıklaması (en güvenilir yol)
                if self._os_level_click(el):
                    self.logger.info(
                        "E-İmza giriş seçildi - OS fare (selector: %s)", sel)
                    return True
                # 2) ActionChains ile fare simülasyonu
                if self._real_click(el):
                    self.logger.info("E-İmza giriş seçildi - fare (selector: %s)", sel)
                    return True
                # 3) Native Selenium click
                try:
                    el.click()
                    self.logger.info("E-İmza giriş seçildi (selector: %s)", sel)
                    return True
                except Exception:
                    self._js_click(el)
                    self.logger.info("E-İmza giriş seçildi - JS (selector: %s)", sel)
                    return True
            except TimeoutException:
                continue
        self.logger.error("E-İmza giriş butonu bulunamadı. config.json içindeki "
                           "'eimza_button_selectors' değerlerini güncelleyin.")
        return False

    def fill_uyap_pin_modal(self, pin, timeout=45):
        """UYAP sayfasında Adalet E-İmza butonuna tıklandıktan sonra sayfada
        AÇILAN HTML modal'daki 'Pin Kodu' input'una PIN'i yazıp 'Giriş' butonuna
        tıklar. PIN penceresi Windows native değil, DOM içinde overlay olduğu
        için doğrudan Selenium ile doldurabiliyoruz. iframe içindeyse ona geçer."""
        if not pin:
            self.logger.info("PIN girilmemiş; modal açıldığında elle giriniz.")
            return False
        self.logger.info("UYAP PIN modal'ı bekleniyor (%s sn)...", timeout)
        pin_selectors = self.config.get("uyap_pin_input_selectors") or [
            "//input[@placeholder='Pin Kodu']",
            "//input[contains(@placeholder,'Pin') and @type='password']",
            "//div[contains(normalize-space(.),'Adalet E-İmza ile Giriş') "
            "or contains(normalize-space(.),'Adalet E-imza')]"
            "//input[@type='password']",
            "input[type='password']",
        ]
        # 1) Ana document
        pin_input, used = self._find_first(pin_selectors, timeout // 2)
        # 2) iframe'ler
        if pin_input is None:
            try:
                self.driver.switch_to.default_content()
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                self.logger.info("Ana document'te PIN yok; %d iframe taranıyor...",
                                 len(iframes))
                for idx, ifr in enumerate(iframes):
                    try:
                        self.driver.switch_to.frame(ifr)
                        pin_input, used = self._find_first(pin_selectors, 3)
                        if pin_input is not None:
                            self.logger.info("PIN alanı iframe %d içinde bulundu.", idx)
                            break
                        self.driver.switch_to.default_content()
                    except Exception:
                        try:
                            self.driver.switch_to.default_content()
                        except Exception:
                            pass
            except Exception:
                pass
        if pin_input is None:
            try:
                self.driver.switch_to.default_content()
            except Exception:
                pass
            self.logger.warning("UYAP PIN alanı DOM'da bulunamadı "
                                "(Adalet E-İmza extension'ı Chrome'da eksik olabilir).")
            return False
        try:
            WebDriverWait(self.driver, 5).until(EC.visibility_of(pin_input))
            pin_input.click()
            pin_input.clear()
            pin_input.send_keys(pin)
            self.logger.info("PIN otomatik yazıldı (selector: %s).", used)
        except Exception as exc:
            self.logger.warning("PIN yazılırken hata: %s", exc)
            return False
        submit_selectors = self.config.get("uyap_pin_submit_selectors") or [
            # PIN modal içindeki Giriş butonu (Pin Kodu alanı ile aynı formda)
            "//input[@placeholder='Pin Kodu']/ancestor::*[self::form or self::div]"
            "//button[contains(normalize-space(.),'Giriş') and "
            "not(contains(normalize-space(.),'İşlemleri')) and "
            "not(contains(normalize-space(.),'E-Devlet')) and "
            "not(contains(normalize-space(.),'Adalet'))]",
            # Genel: modal içinde 'Giriş' yazan buton, hariç tut nav bar / diğer butonlar
            "//button[contains(normalize-space(.),'Giriş') and "
            "not(contains(normalize-space(.),'İşlemleri')) and "
            "not(contains(normalize-space(.),'E-Devlet')) and "
            "not(contains(normalize-space(.),'Adalet E-imza İle')) and "
            "not(contains(normalize-space(.),'ile Giriş'))]",
            "//button[normalize-space(.)='Giriş']",
            "//button[.//span[normalize-space(.)='Giriş']]",
            "button[type='submit']",
        ]
        for sel in submit_selectors:
            try:
                by = By.XPATH if sel.strip().startswith("//") else By.CSS_SELECTOR
                btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((by, sel)))
                self._js_click(btn)
                self.logger.info("PIN modal 'Giriş' butonuna tıklandı.")
                return True
            except TimeoutException:
                continue
        try:
            from selenium.webdriver.common.keys import Keys
            pin_input.send_keys(Keys.ENTER)
            self.logger.info("Giriş butonu bulunamadı; Enter tuşu gönderildi.")
            return True
        except Exception:
            self.logger.warning("PIN gönderilemedi.")
            return False

    def do_mobil_imza(self):
        m = self.config.get("mobil_imza", {})
        wait = self.config.get("timeouts", {}).get("element_wait", 30)
        self.logger.info("Mobil imza (E-Devlet) akışı başlatılıyor...")
        try:
            # 1) 'E-Devlet İle Giriş' açılır menüsü
            self.logger.info("E-Devlet giriş menüsü aranıyor...")
            dd_selectors = [
                m.get("dropdown_selector", ".edevlet-dropdown .dx-dropdownbutton-action"),
                ".edevlet-dropdown .dx-dropdownbutton-action",
                ".edevlet-dropdown",
                "div[title*='E-Devlet']",
            ]
            dropdown, used = self._find_first(dd_selectors, 15)
            if dropdown is None:
                self.logger.error("E-Devlet menüsü sayfada bulunamadı. Sayfa tam "
                                  "yüklenmemiş veya UYAP tasarımı değişmiş olabilir.")
                return False
            self.logger.info("E-Devlet menüsü bulundu (%s), tıklanıyor...", used)
            self._js_click(dropdown)
            time.sleep(1.2)

            # 2) 'Mobil İmza İle Giriş' öğesi
            item_text = m.get("menu_item_text", "Mobil İmza İle Giriş")
            self.logger.info("'%s' seçeneği aranıyor...", item_text)
            item_xpaths = [
                f"//div[contains(@class,'dx-item') and contains(normalize-space(.),'{item_text}')]",
                f"//*[contains(normalize-space(.),'{item_text}')]",
            ]
            item, _ = self._find_first(item_xpaths, 10)
            if item is None:
                self.logger.info("Menü açılmamış olabilir; tekrar deneniyor...")
                self._js_click(dropdown)
                time.sleep(1.2)
                item, _ = self._find_first(item_xpaths, 10)
            if item is None:
                self.logger.error("'%s' menü öğesi bulunamadı.", item_text)
                return False
            self.logger.info("Mobil İmza seçeneği tıklanıyor...")
            self._js_click(item)

            # 3) e-Devlet Kapısı'na gerçekten yönlendik mi?
            self.logger.info("e-Devlet Kapısı sayfası bekleniyor...")
            try:
                WebDriverWait(self.driver, 20).until(
                    lambda d: "turkiye.gov.tr" in (d.current_url or ""))
            except TimeoutException:
                self.logger.error("e-Devlet sayfasına YÖNLENİLEMEDİ. Şu anki adres: %s",
                                  self.driver.current_url)
                return False
            self.logger.info("e-Devlet sayfası açıldı: %s", self.driver.current_url)
            tc_sel = m.get("tc_input_selector", "#tridField")
            phone_sel = m.get("phone_input_selector", "#gsmField")
            submit_sel = m.get("submit_selector", "button[name='submitButton']")
            WebDriverWait(self.driver, wait).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, tc_sel))
            )
            self.logger.info("e-Devlet mobil imza formu açıldı, dolduruluyor...")

            tc = str(m.get("tc_kimlik", "")).strip().replace(" ", "")
            phone = str(m.get("phone", "")).strip()
            # GSM normalizasyonu: e-Devlet 10 hane ister (5XXXXXXXXX)
            phone = "".join(c for c in phone if c.isdigit())
            if phone.startswith("90") and len(phone) == 12:
                phone = phone[2:]
            if phone.startswith("0") and len(phone) == 11:
                phone = phone[1:]
            operator = str(m.get("operator", "turkcell")).strip().lower()
            if tc and len(tc) != 11:
                self.logger.warning("TC kimlik 11 hane olmalı (girilen: %d hane).", len(tc))
            if phone and len(phone) != 10:
                self.logger.warning("GSM 10 hane olmalı, örn 5XXXXXXXXX (girilen: %d hane).", len(phone))
            self.logger.info("Form değerleri: TC=%s..., GSM=%s, Operatör=%s",
                             tc[:3] if tc else "-", phone or "-", operator)

            if tc:
                el = self.driver.find_element(By.CSS_SELECTOR, tc_sel)
                el.clear(); el.send_keys(tc)
            if phone:
                el = self.driver.find_element(By.CSS_SELECTOR, phone_sel)
                el.clear(); el.send_keys(phone)

            op_map = {"turkcell": "#turkcell", "turktelekom": "#turktelekom",
                      "türktelekom": "#turktelekom", "vodafone": "#vodafone"}
            op_sel = op_map.get(operator)
            if op_sel:
                try:
                    el = self.driver.find_element(By.CSS_SELECTOR, op_sel)
                    self.driver.execute_script("arguments[0].click();", el)
                except Exception:
                    self.logger.warning("Operatör radio seçilemedi (%s).", operator)

            if tc and phone:
                el = self.driver.find_element(By.CSS_SELECTOR, submit_sel)
                self.driver.execute_script("arguments[0].click();", el)
                time.sleep(3)
                self.logger.info("Gönderim sonrası sayfa: %s", self.driver.current_url)

                # e-Devlet "teknik aksaklık" hatası verirse form aynı sayfada kalır.
                # Bu durumda 'Devam Et' butonuna basıp yeniden deneriz.
                max_tech_retries = int(m.get("tech_error_retries", 5))
                for attempt in range(1, max_tech_retries + 1):
                    err = self._page_error_text()
                    if not err:
                        break
                    self.logger.error("e-Devlet uyarısı: %s", err)
                    if not self._is_tech_error(err):
                        # Farklı bir hata (ör. yanlış TC/GSM) - retry etme
                        break
                    self.logger.info("Teknik aksaklık algılandı. 'Devam Et' ile "
                                     "yeniden deneniyor (%d/%d)...",
                                     attempt, max_tech_retries)
                    time.sleep(2)
                    retried = self.driver.execute_script("""
                        const btns = Array.from(document.querySelectorAll(
                            "button, input[type=submit], input[type=button], a.btn"));
                        const b = btns.find(x => ((x.innerText || x.value || '')
                            .trim().includes('Devam Et')) && x.offsetParent
                            && x.name !== 'cancelButton');
                        if (b) { b.scrollIntoView({block:'center'}); b.click(); return true; }
                        return false;
                    """)
                    if not retried:
                        self.logger.warning("'Devam Et' butonu bulunamadı, retry durduruldu.")
                        break
                    time.sleep(4)
                    self.logger.info("Yeniden gönderim sonrası sayfa: %s",
                                     self.driver.current_url)

                # e-Devlet bazen ek onay adımı gösterir (İmzala / Onayla / sözleşme)
                for _ in range(3):
                    clicked = self.driver.execute_script("""
                        const texts = ['İmzala', 'Onayla', 'Kabul Ediyorum', 'Devam Et'];
                        const btns = Array.from(document.querySelectorAll(
                            "button, input[type=submit], input[type=button], a.btn"));
                        for (const t of texts) {
                            const b = btns.find(x => ((x.innerText || x.value || '')
                                .trim().includes(t)) && x.offsetParent
                                && !(x.name === 'cancelButton'));
                            if (b) { b.scrollIntoView({block:'center'}); b.click(); return t; }
                        }
                        return '';
                    """)
                    if not clicked:
                        break
                    self.logger.info("e-Devlet ek adımı tıklandı: %s", clicked)
                    time.sleep(3)
                    self.logger.info("Şu anki sayfa: %s", self.driver.current_url)
                    err = self._page_error_text()
                    if err:
                        self.logger.error("e-Devlet uyarısı: %s", err)
                        if self._is_tech_error(err):
                            self.logger.info("Teknik aksaklık; 'Devam Et' tekrar denenecek.")
                            continue
                        break
                self.logger.info("Mobil imza isteği gönderildi. Telefonunuzdan ONAYLAYIN.")
            else:
                self.logger.info("TC Kimlik No / GSM boş. e-Devlet ekranında bilgileri "
                                 "elle girip 'Devam Et'e basın ve telefonunuzdan onaylayın.")
            return True
        except (NoSuchElementException, TimeoutException) as exc:
            self.logger.error("Mobil imza ekranı bulunamadı: %s", exc)
            return False

    # ---------- imza.co (çoklu giriş servisi) ----------
    def do_imzaco(self):
        """
        imza.co üzerinden UYAP'a giriş:
          1) https://imza.co (config'ten alınır) sayfası açılır
          2) kullanıcı adı/şifre doldurulur, Giriş yapılır
          3) panelde 'UYAP' bağlantısı bulunup tıklanır
          4) UYAP paneli açılınca ana wait_login_complete devreye girer

        Sitenin DOM'u değişebileceği için birden çok selector denenir.
        Kullanıcı config.json içinden özel selector geçebilir.
        """
        ic = self.config.get("imzaco", {}) or {}
        url = ic.get("url", "https://imza.co/")
        username = str(ic.get("username", "")).strip()
        password = str(ic.get("password", "")).strip()
        if not username or not password:
            self.logger.error("imza.co kullanıcı adı ve/veya şifresi boş. "
                              "Arayüzden giriniz veya config.json'a yazınız.")
            return False

        self.logger.info("imza.co akışı başlatılıyor: %s", url)
        try:
            self.driver.get(url)
        except Exception as exc:
            self.logger.error("imza.co açılamadı: %s", exc)
            return False

        try:
            WebDriverWait(self.driver, 20).until(
                lambda d: d.execute_script("return document.readyState") == "complete")
        except Exception:
            pass
        time.sleep(1.5)

        # 1) Kullanıcı adı alanı
        user_selectors = ic.get("username_selectors") or [
            "input[name='username']", "input[name='email']",
            "input[name='kullanici']", "input[name='kullaniciAdi']",
            "input[name='user']", "input[name='login']",
            "input[type='email']", "input[type='text']",
            "#username", "#email", "#user", "#login",
        ]
        pw_selectors = ic.get("password_selectors") or [
            "input[name='password']", "input[name='sifre']", "input[name='parola']",
            "input[type='password']", "#password", "#sifre", "#parola",
        ]
        submit_selectors = ic.get("submit_selectors") or [
            "button[type='submit']", "input[type='submit']",
            "//button[contains(normalize-space(.),'Giriş')]",
            "//button[contains(normalize-space(.),'Giris')]",
            "//button[contains(normalize-space(.),'Login')]",
            "//a[contains(normalize-space(.),'Giriş')]",
        ]

        self.logger.info("imza.co giriş formu aranıyor...")
        user_el, used_u = self._find_first(user_selectors, 15)
        if user_el is None:
            self.logger.error("imza.co kullanıcı adı alanı bulunamadı. "
                              "config.imzaco.username_selectors ekleyin.")
            return False
        pw_el, used_p = self._find_first(pw_selectors, 5)
        if pw_el is None:
            self.logger.error("imza.co şifre alanı bulunamadı.")
            return False

        try:
            user_el.clear(); user_el.send_keys(username)
            pw_el.clear(); pw_el.send_keys(password)
            self.logger.info("Form dolduruldu (user: %s, pass: ***).", used_u)
        except Exception as exc:
            self.logger.error("Form doldurulamadı: %s", exc)
            return False

        submit_el, used_s = self._find_first(submit_selectors, 5)
        if submit_el is None:
            self.logger.warning("Giriş butonu bulunamadı. Enter ile denenecek.")
            try:
                from selenium.webdriver.common.keys import Keys
                pw_el.send_keys(Keys.ENTER)
            except Exception:
                pass
        else:
            self.logger.info("Giriş butonuna tıklanıyor (%s)...", used_s)
            try:
                self._js_click(submit_el)
            except Exception:
                try:
                    submit_el.click()
                except Exception as exc:
                    self.logger.error("Giriş butonu tıklanamadı: %s", exc)
                    return False

        # Giriş yanıtı bekle: URL değişimi veya panel elemanı
        try:
            WebDriverWait(self.driver, 20).until(
                lambda d: (d.current_url or "") != url
                or d.execute_script(
                    "return !!document.querySelector('a[href*=\"uyap\"], "
                    "button[data-uyap], .uyap-btn');"))
        except TimeoutException:
            err = self._page_error_text()
            if err:
                self.logger.error("imza.co uyarısı: %s", err)
            self.logger.error("imza.co girişi doğrulanamadı. Sayfa: %s",
                              self.driver.current_url)
            return False
        self.logger.info("imza.co panel sayfası açıldı: %s", self.driver.current_url)

        # 2) Panel içinde UYAP butonunu / linkini tıkla
        uyap_selectors = ic.get("uyap_link_selectors") or [
            "//a[contains(translate(normalize-space(.),'UYAP','uyap'),'uyap')]",
            "//button[contains(translate(normalize-space(.),'UYAP','uyap'),'uyap')]",
            "a[href*='uyap']", "button[data-uyap]",
        ]
        uyap_el, used_uy = self._find_first(uyap_selectors, 20)
        if uyap_el is None:
            self.logger.error("imza.co panelde 'UYAP' bağlantısı bulunamadı. "
                              "config.imzaco.uyap_link_selectors ekleyin.")
            return False
        self.logger.info("UYAP bağlantısı tıklanıyor (%s)...", used_uy)
        try:
            # yeni sekme açılabilir
            handles_before = list(self.driver.window_handles)
            self._js_click(uyap_el)
            time.sleep(2)
            handles_after = list(self.driver.window_handles)
            if len(handles_after) > len(handles_before):
                new_h = [h for h in handles_after if h not in handles_before]
                if new_h:
                    self.driver.switch_to.window(new_h[-1])
                    self.logger.info("Yeni sekmeye geçildi: UYAP")
        except Exception as exc:
            self.logger.error("UYAP linki tıklanamadı: %s", exc)
            return False

        self.logger.info("Şu anki sayfa: %s", self.driver.current_url)
        return True

    def session_error_text(self):
        """Sayfada UYAP bağlantı/oturum hatası görünüyor mu? Varsa metni döndürür.
        Örn: 'UYAP sunucusu ile bağlantı sağlanamadı! Lütfen daha sonra tekrar
        deneyin!' (imza.co panelinde ağ değişince çıkan modal)."""
        markers = self.config.get("session_error_texts") or [
            "sağlanamad",          # bağlantı sağlanamadı
            "oturumunuz sonlan",
            "oturum sonlan",
            "oturum süreniz dol",
            "zaman aşım",
            "yeniden giriş yap",
            "tekrar giriş yap",
        ]
        try:
            self.driver.switch_to.default_content()
        except Exception:
            pass
        try:
            body = self.driver.execute_script(
                "return (document.body && document.body.innerText) || '';") or ""
        except Exception:
            return ""
        low = body.lower()
        for m in markers:
            if m in low:
                idx = low.find(m)
                return " ".join(body[max(0, idx - 60): idx + 120].split())
        return ""

    def _is_tech_error(self, text):
        """e-Devlet'in geçici teknik hata mesajı mı?"""
        if not text:
            return False
        t = text.lower()
        markers = [
            "teknik aksakl",       # "teknik aksaklık"
            "tekrar deneyiniz",
            "işleminiz tamamlanamad",
            "işlem tamamlanamad",
            "daha sonra tekrar",
        ]
        return any(m in t for m in markers)

    def _page_error_text(self):
        try:
            return self.driver.execute_script("""
                const sels = ['.errorContainer', '.warningContainer', '.fieldError',
                              '.error', '.alert', '#loginWarningMessage', '.uyariBox'];
                for (const s of sels) {
                    for (const el of document.querySelectorAll(s)) {
                        const t = (el.innerText || '').trim();
                        if (t && el.offsetParent) return t.slice(0, 300);
                    }
                }
                return '';
            """) or ""
        except Exception:
            return ""

    def wait_login_complete(self):
        timeout = self.config.get("timeouts", {}).get("login_complete_wait", 120)
        success_url = self.config.get("success_url_contains", "")
        not_url = self.config.get("success_url_not_contains", "")
        success_el = self.config.get("success_element_selector", "")
        self.logger.info("Giriş tamamlanması bekleniyor (%s sn)...", timeout)
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                current = (self.driver.current_url or "").lower()
                # e-Devlet ara onay sayfalarını otomatik geçir (Onayla / İzin Ver)
                if "turkiye.gov.tr" in current:
                    allow_devam = "oauth2authorizationserver" in current
                    clicked = self.driver.execute_script("""
                        const allowDevam = arguments[0];
                        const texts = allowDevam
                            ? ['Onayla', 'İzin Ver', 'Devam Et']
                            : ['Onayla', 'İzin Ver'];
                        const bad = ['Redde', 'İptal', 'Vazgeç'];
                        const btns = Array.from(document.querySelectorAll(
                            "button, input[type=submit], input[type=button], a.btn"));
                        for (const t of texts) {
                            const b = btns.find(x => {
                                const s = (x.innerText || x.value || '').trim();
                                return s.includes(t) && x.offsetParent
                                    && !bad.some(w => s.includes(w))
                                    && x.name !== 'cancelButton';
                            });
                            if (b) { b.scrollIntoView({block:'center'}); b.click(); return t; }
                        }
                        return '';
                    """, allow_devam)
                    if clicked:
                        self.logger.info("e-Devlet onay adımı otomatik tıklandı: %s", clicked)
                        time.sleep(2)
                        continue
                if success_url and success_url.lower() in current:
                    self.logger.info("Giriş başarılı (URL eşleşti).")
                    return True
                if not_url and not_url.lower() not in current:
                    err = self.session_error_text()
                    if err:
                        self.logger.warning(
                            "Sayfada bağlantı/oturum hatası görünüyor: %s", err[:150])
                        return False
                    self.logger.info("Giriş başarılı (giriş sayfasından ayrıldı: %s).", current)
                    return True
                if success_el:
                    els = self.driver.find_elements(By.CSS_SELECTOR, success_el)
                    if els:
                        self.logger.info("Giriş başarılı (element bulundu).")
                        return True
            except Exception:
                pass
            time.sleep(1)
        self.logger.warning("Giriş tamamlanma kontrolü zaman aşımına uğradı.")
        return False

    def dismiss_popups(self, passes=1, wait_between=1.5):
        """Giriş sonrası UYAP panelinde açılan duyuru/bildirim pencerelerini
        otomatik kapatır. DevExtreme (dx-popup), Bootstrap modal, SweetAlert
        ve genel role='dialog' pencerelerinde X ikonu veya Kapat/Tamam
        benzeri butonlara tıklar."""
        js = """
            function vis(el, min){
                if(!el) return false;
                min = min || 5;
                var r = el.getBoundingClientRect();
                if (r.width < min || r.height < min) return false;
                var st = window.getComputedStyle(el);
                return st.display !== 'none' && st.visibility !== 'hidden'
                    && parseFloat(st.opacity || '1') > 0.05;
            }
            function fire(el){
                ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(function(t){
                    try{ el.dispatchEvent(new MouseEvent(t,
                        {bubbles:true, cancelable:true, view:window})); }catch(e){}
                });
            }
            var closed = 0;
            var dialogs = Array.from(document.querySelectorAll(
                ".dx-popup-wrapper, .dx-overlay-wrapper, .modal.show, .modal.in, " +
                ".swal2-container, [role='dialog'], [class*='duyuru'], " +
                "[class*='announcement'], [class*='notification-popup']"));
            for (var i = 0; i < dialogs.length; i++){
                var d = dialogs[i];
                if (!vis(d, 30)) continue;
                var dt = (d.innerText || '').toLowerCase();
                // Hata/oturum pencerelerini KAPATMA: izleme döngüsü bunları
                // görüp yeniden giriş başlatmalı.
                var errm = ['sağlanamad', 'oturum sonlan', 'oturumunuz sonlan',
                            'zaman aşım', 'yeniden giriş', 'tekrar giriş'];
                if (errm.some(function(t){ return dt.indexOf(t) !== -1; })) continue;
                var x = d.querySelector(
                    ".dx-closebutton, .dx-icon-close, .swal2-close, " +
                    "button.close, .close, [aria-label*='lose'], [aria-label*='apat']");
                if (x && vis(x)) { fire(x.closest('.dx-button') || x); closed++; continue; }
                var ok = ['Kapat','KAPAT','Tamam','TAMAM','Anladım','ANLADIM',
                          'Daha Sonra','Gösterme','Devam Et'];
                var bad = ['Çıkış','Oturumu Kapat','İptal'];
                var btns = Array.from(d.querySelectorAll(
                    "button, .dx-button, a.btn, input[type=button], input[type=submit]"));
                for (var j = 0; j < btns.length; j++){
                    var s = (btns[j].innerText || btns[j].value || '').trim();
                    if (!s || !vis(btns[j])) continue;
                    if (bad.some(function(t){ return s.indexOf(t) !== -1; })) continue;
                    if (ok.some(function(t){ return s.indexOf(t) !== -1; })){
                        fire(btns[j]); closed++; break;
                    }
                }
            }
            return closed;
        """
        total = 0
        for i in range(passes):
            try:
                self.driver.switch_to.default_content()
            except Exception:
                pass
            try:
                n = int(self.driver.execute_script(js) or 0)
            except Exception:
                n = 0
            if n:
                total += n
                self.logger.info("Bildirim/duyuru penceresi otomatik kapatıldı (%d adet).", n)
            if i < passes - 1:
                time.sleep(wait_between)
        return total

    def run_tasks(self, pin=""):
        """config.post_login_tasks içindeki görevleri çalıştırır."""
        self.run_task_list(self.config.get("post_login_tasks", []), pin)

    def run_task_list(self, tasks, pin=""):
        """
        Verilen görev listesini çalıştırır. Aksiyonlar:
          goto, click, type, wait, select, upload, sign, screenshot
        'sign' aksiyonu: imzala butonuna tıklar; Adalet E-İmza PIN penceresi açılınca
        pin_handler ile PIN otomatik girilir (auto_type_pin ve pin varsa).
        """
        import threading
        from . import pin_handler

        wait = self.config.get("timeouts", {}).get("element_wait", 30)
        for i, task in enumerate(tasks, 1):
            action = task.get("action")
            self.logger.info("Görev %d: %s", i, action)
            try:
                if action == "goto":
                    self.driver.get(task["url"])
                elif action == "click":
                    el = WebDriverWait(self.driver, wait).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, task["selector"]))
                    )
                    el.click()
                elif action == "type":
                    el = self.driver.find_element(By.CSS_SELECTOR, task["selector"])
                    el.clear()
                    el.send_keys(task["text"])
                elif action == "wait":
                    time.sleep(float(task.get("seconds", 1)))
                elif action == "select":
                    from selenium.webdriver.support.ui import Select
                    el = WebDriverWait(self.driver, wait).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, task["selector"]))
                    )
                    Select(el).select_by_visible_text(task["text"])
                elif action == "upload":
                    el = self.driver.find_element(By.CSS_SELECTOR, task["selector"])
                    el.send_keys(task["path"])
                elif action == "sign":
                    # 1) imzala butonuna tıkla
                    el = WebDriverWait(self.driver, wait).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, task["selector"]))
                    )
                    el.click()
                    # 2) açılacak Adalet E-İmza PIN penceresini otomatik doldur
                    if self.config.get("auto_type_pin", True) and pin:
                        stop = {"stop": False}
                        threading.Thread(
                            target=pin_handler.wait_and_fill_pin,
                            args=(pin, self.config, self.logger, stop),
                            daemon=True,
                        ).start()
                    else:
                        self.logger.info("İmzalama PIN penceresini elle giriniz.")
                    time.sleep(float(task.get("wait_after", 3)))
                elif action == "screenshot":
                    self.driver.save_screenshot(task.get("path", "uyap_ekran.png"))
            except Exception as exc:
                self.logger.error("Görev %d başarısız: %s", i, exc)

    def quit(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
