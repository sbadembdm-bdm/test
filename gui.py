"""Tkinter arayüz: modern koyu tema, çoklu profil, mobil imza, tepsi, canlı durum."""
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

try:
    import keyring
    HAS_KEYRING = True
except Exception:
    HAS_KEYRING = False

from .config import load_config, save_config, resolve, profile_names
from .logger import get_logger
from . import runner
from .tray import Tray
from . import report
from . import theme

KEYRING_SERVICE = "bdm-uyap-giris"


def _keyring_user(profile):
    return "pin::%s" % (profile or "Varsayılan")


class UyapApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BDM UYAP GİRİŞ")
        self.root.geometry("780x860")
        self.root.minsize(700, 720)
        theme.apply_style(root)
        self.config = load_config()
        self.logger = None
        self.worker = None
        self.stop_flag = {"stop": False}
        self.history = []
        self.active = self.config.get("active_profile") or (profile_names(self.config) or ["Varsayılan"])[0]
        self._build_ui()
        self._set_icon()
        self._load_profile_into_ui(self.active)
        self._init_tray()
        rec = self.config.pop("_config_recovered", None)
        if rec:
            self.logger.warning(
                "config.json bozuktu ve kurtarıldı. Yedek: %s  |  Hata: %s",
                rec.get("backup"), rec.get("reason"))
            try:
                messagebox.showwarning(
                    "Config Kurtarıldı",
                    "config.json dosyanız bozuktu (elle editleme sırasında JSON "
                    "hatası). Bozuk dosya yedeklendi:\n\n%s\n\nVarsayılan "
                    "ayarlarla devam edilecek. TC/GSM/imza.co gibi bilgileri "
                    "tekrar girip 'Kaydet'e basmanız gerekir." % rec.get("backup"))
            except Exception:
                pass
        if not self.config.get("setup_done"):
            self.root.after(400, self._open_wizard)

    # ---------------- UI ----------------
    def _card(self, title):
        outer = tk.Frame(self.root, bg=theme.CARD)
        outer.pack(fill="x", padx=16, pady=(0, 10))
        tk.Label(outer, text=title, bg=theme.CARD, fg=theme.GOLD,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=14, pady=(9, 0))
        inner = tk.Frame(outer, bg=theme.CARD)
        inner.pack(fill="x", padx=14, pady=(4, 12))
        return inner

    def _mlabel(self, parent, text):
        return tk.Label(parent, text=text, bg=theme.CARD, fg=theme.MUTED,
                        font=theme.FONT_SMALL)

    def _build_ui(self):
        # ---- başlık ----
        header = tk.Frame(self.root, bg=theme.BG)
        header.pack(fill="x", padx=16, pady=(14, 12))
        try:
            from .config import assets_dir
            png = assets_dir() / "icon.png"
            if png.exists():
                img = tk.PhotoImage(file=str(png))
                self._logo = img.subsample(max(1, img.width() // 44))
                tk.Label(header, image=self._logo, bg=theme.BG).pack(side="left", padx=(0, 10))
        except Exception:
            pass
        tbox = tk.Frame(header, bg=theme.BG)
        tbox.pack(side="left")
        tk.Label(tbox, text="BDM UYAP GİRİŞ", bg=theme.BG, fg=theme.TEXT,
                 font=("Segoe UI", 15, "bold")).pack(anchor="w")
        tk.Label(tbox, text="E-imza ile otomatik UYAP girişi", bg=theme.BG,
                 fg=theme.MUTED, font=theme.FONT_SMALL).pack(anchor="w")

        pbox = tk.Frame(header, bg=theme.BG)
        pbox.pack(side="right")
        tk.Label(pbox, text="Profil", bg=theme.BG, fg=theme.MUTED,
                 font=theme.FONT_SMALL).pack(anchor="w")
        prow = tk.Frame(pbox, bg=theme.BG)
        prow.pack()
        self.profile_var = tk.StringVar(value=self.active)
        self.profile_cb = ttk.Combobox(prow, textvariable=self.profile_var,
                                       values=profile_names(self.config),
                                       state="readonly", width=15)
        self.profile_cb.pack(side="left")
        self.profile_cb.bind("<<ComboboxSelected>>", self._on_profile_change)
        ttk.Button(prow, text="+", width=3, command=self.on_new_profile).pack(side="left", padx=(6, 2))
        ttk.Button(prow, text="−", width=3, command=self.on_delete_profile).pack(side="left")

        # ---- bağlantı kartı ----
        con = self._card("BAĞLANTI")
        self._mlabel(con, "Portal Adresi").pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(con, textvariable=self.url_var).pack(fill="x", pady=(2, 8))

        crow = tk.Frame(con, bg=theme.CARD)
        crow.pack(fill="x")
        self._mlabel(crow, "Yöntem").pack(side="left")
        self.method_var = tk.StringVar()
        ttk.Combobox(crow, textvariable=self.method_var,
                     values=["eimza", "mobil", "imzaco"],
                     state="readonly", width=8).pack(side="left", padx=(4, 14))
        self._mlabel(crow, "Tarayıcı").pack(side="left")
        self.browser_var = tk.StringVar()
        ttk.Combobox(crow, textvariable=self.browser_var, values=["chrome", "edge"],
                     state="readonly", width=8).pack(side="left", padx=(4, 14))
        self.own_profile_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(crow, text="Kendi Chrome profilim",
                        variable=self.own_profile_var).pack(side="left", padx=(0, 6))
        self._mlabel(crow, "Profil:").pack(side="left")
        self.profile_name_var = tk.StringVar(value="Default")
        self.chrome_profile_cb = ttk.Combobox(
            crow, textvariable=self.profile_name_var, width=16,
            values=self._detect_chrome_profiles_list())
        self.chrome_profile_cb.pack(side="left", padx=4)
        ttk.Button(crow, text="↻ Yenile", width=9,
                   command=self._refresh_chrome_profiles).pack(side="left")

        crow2 = tk.Frame(con, bg=theme.CARD)
        crow2.pack(fill="x", pady=(6, 0))
        self.fallback_var = tk.BooleanVar(
            value=self.config.get("fallback_to_mobil", True))
        ttk.Checkbutton(crow2,
                        text="E-imza başarısızsa mobil imza ile dene (fallback)",
                        variable=self.fallback_var).pack(side="left")
        ttk.Button(crow2, text="🗑  Klonu Sıfırla",
                   command=self._reset_chrome_clone).pack(side="right")

        # ---- kimlik kartı ----
        idc = self._card("KİMLİK / PIN")
        pinrow = tk.Frame(idc, bg=theme.CARD)
        pinrow.pack(fill="x")
        self._mlabel(pinrow, "Akıllı Kart PIN").pack(side="left")
        self.pin_var = tk.StringVar()
        ttk.Entry(pinrow, textvariable=self.pin_var, show="•", width=16).pack(side="left", padx=(6, 14))
        self.auto_pin_var = tk.BooleanVar(value=self.config.get("auto_type_pin", True))
        ttk.Checkbutton(pinrow, text="PIN otomatik gir",
                        variable=self.auto_pin_var).pack(side="left", padx=(0, 10))
        self.remember_var = tk.BooleanVar(value=False)
        self.remember_cb = ttk.Checkbutton(pinrow, text="PIN'i güvenli sakla",
                                           variable=self.remember_var)
        self.remember_cb.pack(side="left")
        if not HAS_KEYRING:
            self.remember_cb.state(["disabled"])

        mrow = tk.Frame(idc, bg=theme.CARD)
        mrow.pack(fill="x", pady=(8, 0))
        self._mlabel(mrow, "Mobil imza  —  TC:").pack(side="left")
        self.tc_var = tk.StringVar()
        ttk.Entry(mrow, textvariable=self.tc_var, width=13).pack(side="left", padx=(4, 10))
        self._mlabel(mrow, "GSM:").pack(side="left")
        self.phone_var = tk.StringVar()
        ttk.Entry(mrow, textvariable=self.phone_var, width=13).pack(side="left", padx=(4, 10))
        self._mlabel(mrow, "Operatör:").pack(side="left")
        self.operator_var = tk.StringVar()
        ttk.Combobox(mrow, textvariable=self.operator_var,
                     values=["turkcell", "turktelekom", "vodafone"],
                     state="readonly", width=11).pack(side="left", padx=4)

        irow = tk.Frame(idc, bg=theme.CARD)
        irow.pack(fill="x", pady=(8, 0))
        self._mlabel(irow, "imza.co  —  Kullanıcı:").pack(side="left")
        self.imzaco_user_var = tk.StringVar()
        ttk.Entry(irow, textvariable=self.imzaco_user_var, width=20).pack(side="left", padx=(4, 10))
        self._mlabel(irow, "Şifre:").pack(side="left")
        self.imzaco_pw_var = tk.StringVar()
        ttk.Entry(irow, textvariable=self.imzaco_pw_var, show="•",
                  width=16).pack(side="left", padx=(4, 10))
        self.imzaco_remember_var = tk.BooleanVar(value=False)
        self.imzaco_remember_cb = ttk.Checkbutton(irow, text="Şifreyi güvenli sakla",
                                                  variable=self.imzaco_remember_var)
        self.imzaco_remember_cb.pack(side="left")
        if not HAS_KEYRING:
            self.imzaco_remember_cb.state(["disabled"])

        # ---- otomasyon kartı ----
        opt = self._card("OTOMASYON")
        orow = tk.Frame(opt, bg=theme.CARD)
        orow.pack(fill="x")
        self.watch_var = tk.BooleanVar(value=self.config.get("auto_watch", False))
        ttk.Checkbutton(orow, text="UYAP'ı izle & otomatik giriş",
                        variable=self.watch_var).pack(side="left", padx=(0, 12))
        self.notif_var = tk.BooleanVar(value=self.config.get("notifications", True))
        ttk.Checkbutton(orow, text="Bildirim", variable=self.notif_var).pack(side="left", padx=(0, 12))
        sch = self.config.get("schedule", {})
        self.sched_var = tk.BooleanVar(value=sch.get("enabled", False))
        ttk.Checkbutton(orow, text="Sadece mesai:", variable=self.sched_var).pack(side="left")
        self.sched_start = tk.StringVar(value=sch.get("start", "09:00"))
        self.sched_end = tk.StringVar(value=sch.get("end", "18:00"))
        ttk.Entry(orow, textvariable=self.sched_start, width=6).pack(side="left", padx=(4, 2))
        tk.Label(orow, text="–", bg=theme.CARD, fg=theme.MUTED).pack(side="left")
        ttk.Entry(orow, textvariable=self.sched_end, width=6).pack(side="left", padx=(2, 0))

        # ---- butonlar ----
        brow = tk.Frame(self.root, bg=theme.BG)
        brow.pack(fill="x", padx=16, pady=(2, 10))
        self.start_btn = ttk.Button(brow, text="▶  Giriş Yap", style="Accent.TButton",
                                    command=self.on_start)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(brow, text="■  Durdur", style="Danger.TButton",
                                   command=self.on_stop, state="disabled")
        self.stop_btn.pack(side="left", padx=(8, 16))
        ttk.Button(brow, text="Kaydet", command=self.on_save).pack(side="left", padx=(0, 6))
        ttk.Button(brow, text="Görevler", command=self.on_tasks).pack(side="left", padx=(0, 6))
        ttk.Button(brow, text="Geçmiş", command=self.on_history).pack(side="left", padx=(0, 6))
        ttk.Button(brow, text="Rapor", command=self.on_export_report).pack(side="left")

        # ---- durum ----
        self.status_lbl = tk.Label(self.root, text="●  HAZIR", fg="white", bg="#24377f",
                                   font=("Segoe UI", 10, "bold"), anchor="w", padx=12, pady=7)
        self.status_lbl.pack(fill="x", padx=16)

        # ---- log ----
        logframe = tk.Frame(self.root, bg=theme.BG)
        logframe.pack(fill="both", expand=True, padx=16, pady=(8, 14))
        tk.Label(logframe, text="KAYITLAR", bg=theme.BG, fg=theme.MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 3))
        logbox = tk.Frame(logframe, bg=theme.LOG_BG)
        logbox.pack(fill="both", expand=True)
        self.log_text = tk.Text(logbox, state="disabled", bg=theme.LOG_BG,
                                fg=theme.LOG_FG, insertbackground=theme.LOG_FG,
                                relief="flat", font=("Consolas", 9),
                                padx=10, pady=8, highlightthickness=0)
        self.log_text.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(logbox, orient="vertical", command=self.log_text.yview)
        sb.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=sb.set)

        self.logger = get_logger(self._append_log)
        from . import __version__
        self.logger.info("BDM UYAP GİRİŞ başlatıldı — Sürüm %s", __version__)

    def _set_icon(self):
        try:
            from .config import assets_dir
            ico = assets_dir() / "icon.ico"
            png = assets_dir() / "icon.png"
            if ico.exists():
                self.root.iconbitmap(str(ico))
            elif png.exists():
                self._icon_img = tk.PhotoImage(file=str(png))
                self.root.iconphoto(True, self._icon_img)
        except Exception:
            pass

    def on_tasks(self):
        from .task_gui import TaskManagerWindow

        def apply(tasks):
            self.config["scheduled_tasks"] = tasks
            save_config(self.config)
            self.logger.info("Zamanlı görevler kaydedildi (%d görev).", len(tasks))

        TaskManagerWindow(self.root, self.config, apply)

    def on_history(self):
        if not self.history:
            messagebox.showinfo("Geçmiş", "Henüz kayıt yok. Giriş veya izleme "
                                          "başlattığınızda burada birikir.")
            return
        from .history_gui import HistoryWindow
        HistoryWindow(self.root, self.history)

    def _open_wizard(self):
        from .wizard import SetupWizard
        SetupWizard(self.root, self)

    def finish_setup(self, silent=False):
        self._store_ui_into_profile()
        self._sync_globals()
        self.config["setup_done"] = True
        self.config["active_profile"] = self.active
        save_config(self.config)
        if not silent:
            self.logger.info("Kurulum sihirbazı tamamlandı; ayarlar kaydedildi.")

    # ---------------- tray ----------------
    def _init_tray(self):
        self.tray = Tray(
            on_show=lambda: self.root.after(0, self._show_window),
            on_start=lambda: self.root.after(0, self.on_start),
            on_stop=lambda: self.root.after(0, self.on_stop),
            on_quit=lambda: self.root.after(0, self._real_quit),
        )
        started = self.tray.start()
        if started and self.config.get("minimize_to_tray", True):
            self.root.protocol("WM_DELETE_WINDOW", self._hide_window)
        else:
            self.root.protocol("WM_DELETE_WINDOW", self._real_quit)

    def _hide_window(self):
        self.root.withdraw()
        if getattr(self, "tray", None):
            self.tray.notify("BDM UYAP GİRİŞ", "Tepside çalışmaya devam ediyor.")

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()

    def _real_quit(self):
        self.stop_flag["stop"] = True
        if getattr(self, "tray", None):
            self.tray.stop()
        self.root.destroy()

    # ---------------- profil ----------------
    def _profile(self, name=None):
        return self.config["profiles"][name or self.active]

    def _load_profile_into_ui(self, name):
        self.active = name
        p = self._profile(name)
        self.url_var.set(p.get("portal_url", ""))
        self.method_var.set(p.get("login_method", "eimza"))
        self.browser_var.set(p.get("browser", "chrome"))
        self.own_profile_var.set(bool(p.get("use_existing_profile")))
        self.profile_name_var.set(p.get("chrome_profile_name", "Default"))
        mi = p.get("mobil_imza", {})
        self.tc_var.set(mi.get("tc_kimlik", ""))
        self.phone_var.set(mi.get("phone", ""))
        self.operator_var.set(mi.get("operator", "turkcell"))
        ic = p.get("imzaco", {})
        self.imzaco_user_var.set(ic.get("username", ""))
        self.imzaco_pw_var.set("")
        self.imzaco_remember_var.set(False)
        if HAS_KEYRING:
            saved_pw = self._get_saved_imzaco(name)
            if saved_pw:
                self.imzaco_pw_var.set(saved_pw)
                self.imzaco_remember_var.set(True)
        self.pin_var.set("")
        self.remember_var.set(False)
        if HAS_KEYRING:
            saved = self._get_saved_pin(name)
            if saved:
                self.pin_var.set(saved)
                self.remember_var.set(True)

    def _store_ui_into_profile(self):
        p = self._profile()
        p["portal_url"] = self.url_var.get().strip()
        p["login_method"] = self.method_var.get()
        p["browser"] = self.browser_var.get()
        p["use_existing_profile"] = self.own_profile_var.get()
        # "Default — bdmhukuk@gmail.com" gibi seçildiyse sadece klasör adını al
        raw = self.profile_name_var.get().strip() or "Default"
        p["chrome_profile_name"] = raw.split(" — ")[0].strip() or "Default"
        mi = p.setdefault("mobil_imza", {})
        mi["tc_kimlik"] = self.tc_var.get().strip()
        mi["phone"] = self.phone_var.get().strip()
        mi["operator"] = self.operator_var.get()
        ic = p.setdefault("imzaco", {})
        ic.setdefault("url", "https://imza.co/")
        ic["username"] = self.imzaco_user_var.get().strip()
        # Şifre dosyaya yazılmaz, keyring'e alınır (aşağıda on_start / on_save)
        ic["password"] = ""

    def _on_profile_change(self, _evt=None):
        self._store_ui_into_profile()
        self._load_profile_into_ui(self.profile_var.get())
        self.config["active_profile"] = self.active
        self.logger.info("Profil değiştirildi: %s", self.active)

    def on_new_profile(self):
        name = simpledialog.askstring("Yeni Profil", "Profil adı:", parent=self.root)
        if not name:
            return
        if name in self.config["profiles"]:
            messagebox.showwarning("Var", "Bu isimde profil zaten var.")
            return
        import copy
        self._store_ui_into_profile()
        self.config["profiles"][name] = copy.deepcopy(self._profile())
        self.profile_cb.configure(values=profile_names(self.config))
        self.profile_var.set(name)
        self._load_profile_into_ui(name)
        self.config["active_profile"] = name
        self.logger.info("Yeni profil eklendi: %s", name)

    def on_delete_profile(self):
        if len(self.config["profiles"]) <= 1:
            messagebox.showwarning("Engellendi", "En az bir profil kalmalı.")
            return
        name = self.active
        if not messagebox.askyesno("Sil", "'%s' profili silinsin mi?" % name):
            return
        del self.config["profiles"][name]
        if HAS_KEYRING:
            self._delete_pin(name)
        remaining = profile_names(self.config)
        self.profile_cb.configure(values=remaining)
        self.profile_var.set(remaining[0])
        self._load_profile_into_ui(remaining[0])
        self.config["active_profile"] = remaining[0]

    # ---------------- keyring ----------------
    def _get_saved_pin(self, profile):
        try:
            return keyring.get_password(KEYRING_SERVICE, _keyring_user(profile))
        except Exception:
            return None

    def _save_pin(self, profile, pin):
        try:
            keyring.set_password(KEYRING_SERVICE, _keyring_user(profile), pin)
        except Exception as exc:
            self.logger.error("PIN kaydedilemedi: %s", exc)

    def _delete_pin(self, profile):
        try:
            keyring.delete_password(KEYRING_SERVICE, _keyring_user(profile))
        except Exception:
            pass

    def _imzaco_key(self, profile):
        return "imzaco::%s" % (profile or "Varsayılan")

    def _get_saved_imzaco(self, profile):
        try:
            return keyring.get_password(KEYRING_SERVICE, self._imzaco_key(profile))
        except Exception:
            return None

    def _save_imzaco(self, profile, pw):
        try:
            keyring.set_password(KEYRING_SERVICE, self._imzaco_key(profile), pw)
        except Exception as exc:
            self.logger.error("imza.co şifresi kaydedilemedi: %s", exc)

    def _delete_imzaco(self, profile):
        try:
            keyring.delete_password(KEYRING_SERVICE, self._imzaco_key(profile))
        except Exception:
            pass

    # ---------------- log & durum ----------------
    def _append_log(self, msg):
        def append():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.root.after(0, append)

    def _set_status(self, state, msg):
        palette = {
            "up": ("#1a7f37", "●  UYAP AYAKTA"),
            "logged_in": ("#1a7f37", "●  GİRİŞ YAPILDI"),
            "login": ("#b26a00", "●  GİRİŞ YAPILIYOR"),
            "down": ("#b42318", "●  UYAP DÜŞÜK"),
            "error": ("#b42318", "●  HATA"),
            "offhours": ("#555555", "●  MESAİ DIŞI"),
            "idle": ("#24377f", "●  HAZIR"),
        }
        color, label = palette.get(state, ("#24377f", "●  " + str(state).upper()))
        text = "%s   —   %s" % (label, msg) if msg else label

        from datetime import datetime
        self.history.append((datetime.now().strftime("%Y-%m-%d %H:%M:%S"), state, msg))
        if len(self.history) > 2000:
            self.history = self.history[-2000:]

        def apply():
            self.status_lbl.configure(bg=color, text=text)
        self.root.after(0, apply)
        if getattr(self, "tray", None):
            self.tray.set_status(state, msg)

    # ---------------- actions ----------------
    def _detect_chrome_profiles_list(self):
        """Chrome User Data altındaki profilleri 'Klasör — display_name (user_name)'
        formatında listeler. Bu görsel etikete rağmen kullanıcının Kaydet'te
        seçtiği değer sadece klasör adı (Default, Profile 1...) olur."""
        try:
            import json as _json
            base = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
            if not os.path.isdir(base):
                return ["Default"]
            info = {}
            ls = os.path.join(base, "Local State")
            if os.path.exists(ls):
                try:
                    with open(ls, "r", encoding="utf-8") as f:
                        d = _json.load(f)
                    info = (d.get("profile") or {}).get("info_cache", {}) or {}
                except Exception:
                    pass
            out = []
            for name in sorted(os.listdir(base)):
                if not os.path.isdir(os.path.join(base, name)):
                    continue
                if name != "Default" and not name.startswith("Profile"):
                    continue
                meta = info.get(name, {}) or {}
                label = "%s — %s" % (name, meta.get("user_name")
                                     or meta.get("name") or "profil")
                out.append(label)
            return out or ["Default"]
        except Exception:
            return ["Default"]

    def _refresh_chrome_profiles(self):
        self.chrome_profile_cb["values"] = self._detect_chrome_profiles_list()

    def _reset_chrome_clone(self):
        """Klonlanmış Chrome profil dizinini siler; bir sonraki başlatmada
        seçili gerçek profil sıfırdan yeniden kopyalanır (uzantılar dahil)."""
        clone = os.path.expandvars(r"%LOCALAPPDATA%\BDM-UYAP-GIRIS\ChromeProfile")
        if not os.path.isdir(clone):
            messagebox.showinfo("Klon Sıfırla", "Klon zaten mevcut değil.")
            return
        if not messagebox.askyesno(
                "Klonu Sıfırla",
                "Otomasyon için oluşturulan Chrome klonu silinecek. Bir sonraki "
                "girişte seçili profil (uzantılar dahil) sıfırdan kopyalanacak.\n\n"
                "Devam edilsin mi?"):
            return
        try:
            import shutil
            shutil.rmtree(clone, ignore_errors=True)
            self.logger.info("Klon Chrome profili silindi: %s", clone)
            messagebox.showinfo("Klon Sıfırla",
                                "Klon silindi. 'Giriş Yap' dediğinizde yeniden "
                                "kopyalanacak.")
        except Exception as exc:
            self.logger.error("Klon silinemedi: %s", exc)
            messagebox.showerror("Klon Sıfırla", "Klon silinemedi: %s" % exc)

    def _sync_globals(self):
        self.config["auto_type_pin"] = self.auto_pin_var.get()
        self.config["auto_watch"] = self.watch_var.get()
        self.config["notifications"] = self.notif_var.get()
        self.config["fallback_to_mobil"] = self.fallback_var.get()
        sch = self.config.setdefault("schedule", {})
        sch["enabled"] = self.sched_var.get()
        sch["start"] = self.sched_start.get().strip() or "09:00"
        sch["end"] = self.sched_end.get().strip() or "18:00"

    def on_save(self):
        self._store_ui_into_profile()
        self._sync_globals()
        self.config["active_profile"] = self.active
        save_config(self.config)
        messagebox.showinfo("Kaydedildi", "Ayarlar config.json'a kaydedildi.")

    def on_stop(self):
        self.stop_flag["stop"] = True
        self.logger.info("Durdurma istendi...")
        self.stop_btn.state(["disabled"])

    def on_export_report(self):
        if not self.history:
            messagebox.showinfo("Rapor", "Henüz kaydedilecek olay yok.")
            return
        path = filedialog.asksaveasfilename(
            title="Raporu Kaydet",
            defaultextension=".csv",
            initialfile=report.default_report_name(),
            filetypes=[("CSV", "*.csv"), ("Metin", "*.txt")],
        )
        if not path:
            return
        try:
            report.write_report(path, self.history)
            self.logger.info("Rapor kaydedildi: %s", path)
            messagebox.showinfo("Rapor", "Rapor kaydedildi:\n%s" % path)
        except Exception as exc:
            messagebox.showerror("Hata", "Rapor kaydedilemedi: %s" % exc)

    def _chrome_running(self):
        try:
            import subprocess
            out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq chrome.exe"],
                                 capture_output=True, text=True,
                                 creationflags=0x08000000)
            return "chrome.exe" in (out.stdout or "").lower()
        except Exception:
            return False

    def on_start(self):
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("Çalışıyor", "İşlem zaten sürüyor.")
            return

        # Not: Klonlanmış Chrome profili kullandığımız için kullanıcının açık
        # Chrome pencerelerine dokunmuyoruz. Klon ayrı bir user-data-dir'de
        # çalışır, aynı anda kendi Chrome'unuz da açık kalabilir.

        self._store_ui_into_profile()
        self._sync_globals()
        self.config["active_profile"] = self.active
        pin = self.pin_var.get()

        if HAS_KEYRING:
            if self.remember_var.get() and pin:
                self._save_pin(self.active, pin)
            elif not self.remember_var.get():
                self._delete_pin(self.active)
            imzaco_pw = self.imzaco_pw_var.get()
            if self.imzaco_remember_var.get() and imzaco_pw:
                self._save_imzaco(self.active, imzaco_pw)
            elif not self.imzaco_remember_var.get():
                self._delete_imzaco(self.active)

        flat = resolve(self.config, self.active)
        # imza.co şifresi dosyaya yazılmaz; keyring/UI'dan alınıp runtime'a enjekte edilir
        imzaco_pw = self.imzaco_pw_var.get() or (
            self._get_saved_imzaco(self.active) if HAS_KEYRING else "")
        if imzaco_pw:
            flat.setdefault("imzaco", {})["password"] = imzaco_pw
        self.stop_flag = {"stop": False}
        self.start_btn.state(["disabled"])

        if self.watch_var.get():
            self.logger.info("=== İzleme modu (%s) ===", self.active)
            self.stop_btn.state(["!disabled"])

            def done():
                self.root.after(0, lambda: self.start_btn.state(["!disabled"]))
                self.root.after(0, lambda: self.stop_btn.state(["disabled"]))

            def target():
                try:
                    runner.run_watch(flat, pin, self.logger, self.stop_flag,
                                     state_cb=self._set_status)
                finally:
                    done()

            self.worker = threading.Thread(target=target, daemon=True)
        else:
            self.logger.info("=== Giriş (%s) ===", self.active)

            def finish(_ok):
                self.root.after(0, lambda: self.start_btn.state(["!disabled"]))

            self.worker = threading.Thread(
                target=runner.run_login,
                args=(flat, pin, self.logger, self.stop_flag, finish),
                kwargs={"state_cb": self._set_status},
                daemon=True,
            )
        self.worker.start()


def main():
    root = tk.Tk()
    UyapApp(root)
    root.mainloop()
