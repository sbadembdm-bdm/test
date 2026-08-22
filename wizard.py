"""İlk açılışta adım adım kurulum sihirbazı."""
import tkinter as tk
from tkinter import ttk

from . import theme


class SetupWizard(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("Kurulum Sihirbazı")
        self.configure(bg=theme.BG)
        self.geometry("620x470")
        self.resizable(False, False)
        self.step = 0
        self.steps = []
        self._build()
        self._show()
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._skip)

    def _mk_step(self, title, desc):
        f = tk.Frame(self.body, bg=theme.CARD)
        tk.Label(f, text=title, bg=theme.CARD, fg=theme.GOLD,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=18, pady=(16, 2))
        tk.Label(f, text=desc, bg=theme.CARD, fg=theme.MUTED, justify="left",
                 wraplength=540, font=theme.FONT_SMALL).pack(anchor="w", padx=18, pady=(0, 12))
        inner = tk.Frame(f, bg=theme.CARD)
        inner.pack(fill="x", padx=18)
        self.steps.append(f)
        return inner

    def _row(self, parent, label):
        r = tk.Frame(parent, bg=theme.CARD)
        r.pack(fill="x", pady=5)
        tk.Label(r, text=label, bg=theme.CARD, fg=theme.TEXT, width=16,
                 anchor="w", font=theme.FONT_SMALL).pack(side="left")
        return r

    def _build(self):
        a = self.app
        tk.Label(self, text="BDM UYAP GİRİŞ — Hızlı Kurulum", bg=theme.BG,
                 fg=theme.TEXT, font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=18, pady=(14, 8))
        self.body = tk.Frame(self, bg=theme.BG)
        self.body.pack(fill="both", expand=True, padx=18)

        s = self._mk_step("1. Bağlantı", "UYAP portal adresi ve giriş yönteminizi seçin.")
        r = self._row(s, "Portal Adresi")
        ttk.Entry(r, textvariable=a.url_var, width=44).pack(side="left")
        r = self._row(s, "Giriş Yöntemi")
        ttk.Combobox(r, textvariable=a.method_var,
                     values=["eimza", "mobil", "imzaco"],
                     state="readonly", width=10).pack(side="left")
        r = self._row(s, "Tarayıcı")
        ttk.Combobox(r, textvariable=a.browser_var, values=["chrome", "edge"],
                     state="readonly", width=10).pack(side="left")
        r = self._row(s, "")
        ttk.Checkbutton(r, text="Eklentilerimin kurulu olduğu kendi Chrome profilimi kullan",
                        variable=a.own_profile_var).pack(side="left")

        s = self._mk_step("2. E-İmza PIN",
                          "Akıllı kart PIN'inizi girin. 'Güvenli sakla' işaretlerseniz "
                          "PIN Windows kimlik kasasında şifreli saklanır.")
        r = self._row(s, "Akıllı Kart PIN")
        ttk.Entry(r, textvariable=a.pin_var, show="•", width=18).pack(side="left")
        r = self._row(s, "")
        ttk.Checkbutton(r, text="PIN'i otomatik gir",
                        variable=a.auto_pin_var).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(r, text="PIN'i güvenli sakla",
                        variable=a.remember_var).pack(side="left")

        s = self._mk_step("3. Mobil İmza (Yedek)",
                          "Kart takılı olmadığında e-Devlet mobil imza ile giriş denenir. "
                          "İsteğe bağlıdır, boş bırakabilirsiniz.")
        r = self._row(s, "TC Kimlik")
        ttk.Entry(r, textvariable=a.tc_var, width=15).pack(side="left")
        r = self._row(s, "Telefon (GSM)")
        ttk.Entry(r, textvariable=a.phone_var, width=15).pack(side="left")
        r = self._row(s, "Operatör")
        ttk.Combobox(r, textvariable=a.operator_var,
                     values=["turkcell", "turktelekom", "vodafone"],
                     state="readonly", width=12).pack(side="left")

        s = self._mk_step("4. imza.co (Çoklu Giriş)",
                          "Ofiste imza.co çoklu giriş servisi kullanıyorsanız kullanıcı "
                          "adı ve şifrenizi girin. Şifre Windows kimlik kasasında "
                          "şifreli saklanır. Boş bırakırsanız devre dışıdır.")
        r = self._row(s, "Kullanıcı Adı")
        ttk.Entry(r, textvariable=a.imzaco_user_var, width=28).pack(side="left")
        r = self._row(s, "Şifre")
        ttk.Entry(r, textvariable=a.imzaco_pw_var, show="•", width=22).pack(side="left")
        r = self._row(s, "")
        ttk.Checkbutton(r, text="Şifreyi güvenli sakla",
                        variable=a.imzaco_remember_var).pack(side="left")

        s = self._mk_step("5. Otomasyon",
                          "İzleme açıkken UYAP düşüp kalktığında otomatik tekrar giriş yapılır.")
        r = self._row(s, "")
        ttk.Checkbutton(r, text="UYAP'ı izle & otomatik giriş",
                        variable=a.watch_var).pack(side="left")
        r = self._row(s, "")
        ttk.Checkbutton(r, text="Masaüstü bildirimleri",
                        variable=a.notif_var).pack(side="left")
        r = self._row(s, "Mesai saatleri")
        ttk.Checkbutton(r, text="Sadece", variable=a.sched_var).pack(side="left")
        ttk.Entry(r, textvariable=a.sched_start, width=6).pack(side="left", padx=(6, 2))
        tk.Label(r, text="–", bg=theme.CARD, fg=theme.MUTED).pack(side="left")
        ttk.Entry(r, textvariable=a.sched_end, width=6).pack(side="left", padx=(2, 0))

        nav = tk.Frame(self, bg=theme.BG)
        nav.pack(fill="x", padx=18, pady=14)
        self.pos_lbl = tk.Label(nav, text="", bg=theme.BG, fg=theme.MUTED,
                                font=theme.FONT_SMALL)
        self.pos_lbl.pack(side="left")
        self.next_btn = ttk.Button(nav, text="İleri  ▶", style="Accent.TButton",
                                   command=self._next)
        self.next_btn.pack(side="right")
        self.back_btn = ttk.Button(nav, text="◀  Geri", command=self._back)
        self.back_btn.pack(side="right", padx=8)
        ttk.Button(nav, text="Atla", command=self._skip).pack(side="right", padx=8)

    def _show(self):
        for f in self.steps:
            f.pack_forget()
        self.steps[self.step].pack(fill="both", expand=True)
        self.pos_lbl.configure(text="Adım %d / %d" % (self.step + 1, len(self.steps)))
        self.back_btn.state(["!disabled"] if self.step > 0 else ["disabled"])
        self.next_btn.configure(
            text="Bitir  ✔" if self.step == len(self.steps) - 1 else "İleri  ▶")

    def _next(self):
        if self.step < len(self.steps) - 1:
            self.step += 1
            self._show()
        else:
            self.app.finish_setup()
            self.destroy()

    def _back(self):
        if self.step > 0:
            self.step -= 1
            self._show()

    def _skip(self):
        self.app.finish_setup(silent=True)
        self.destroy()
