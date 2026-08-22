"""Durum geçmişi penceresi: tarih ve durum filtresi + dışa aktarma."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from . import theme, report

STATES = ["Tümü", "logged_in", "login", "up", "down", "error", "offhours", "idle"]


class HistoryWindow(tk.Toplevel):
    def __init__(self, parent, history):
        super().__init__(parent)
        self.title("Geçmiş")
        self.configure(bg=theme.BG)
        self.geometry("840x540")
        self.history = list(history)
        self._build()
        self._fill()
        self.transient(parent)

    def _build(self):
        bar = tk.Frame(self, bg=theme.BG)
        bar.pack(fill="x", padx=14, pady=12)
        tk.Label(bar, text="Tarih (YYYY-AA-GG):", bg=theme.BG, fg=theme.MUTED,
                 font=theme.FONT_SMALL).pack(side="left")
        self.date_var = tk.StringVar()
        ttk.Entry(bar, textvariable=self.date_var, width=12).pack(side="left", padx=(4, 12))
        tk.Label(bar, text="Durum:", bg=theme.BG, fg=theme.MUTED,
                 font=theme.FONT_SMALL).pack(side="left")
        self.state_var = tk.StringVar(value="Tümü")
        ttk.Combobox(bar, textvariable=self.state_var, values=STATES,
                     state="readonly", width=11).pack(side="left", padx=(4, 12))
        ttk.Button(bar, text="Filtrele", command=self._fill).pack(side="left")
        ttk.Button(bar, text="Temizle", command=self._clear).pack(side="left", padx=6)
        ttk.Button(bar, text="Dışa Aktar", command=self._export).pack(side="right")

        box = tk.Frame(self, bg=theme.BG)
        box.pack(fill="both", expand=True, padx=14, pady=(0, 4))
        self.tree = ttk.Treeview(box, columns=("zaman", "durum", "mesaj"), show="headings")
        for cid, txt, w in (("zaman", "Zaman", 150), ("durum", "Durum", 95), ("mesaj", "Mesaj", 540)):
            self.tree.heading(cid, text=txt)
            self.tree.column(cid, width=w, stretch=(cid == "mesaj"))
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        sb.pack(side="left", fill="y")
        self.tree.configure(yscrollcommand=sb.set)
        self.count_lbl = tk.Label(self, text="", bg=theme.BG, fg=theme.MUTED,
                                  font=theme.FONT_SMALL)
        self.count_lbl.pack(anchor="w", padx=14, pady=(4, 10))

    def _rows(self):
        d = self.date_var.get().strip()
        s = self.state_var.get()
        out = []
        for ts, state, msg in self.history:
            if d and not ts.startswith(d):
                continue
            if s != "Tümü" and state != s:
                continue
            out.append((ts, state, msg))
        return out

    def _fill(self):
        self.tree.delete(*self.tree.get_children())
        rows = self._rows()
        for r in rows:
            self.tree.insert("", "end", values=r)
        self.count_lbl.configure(text="%d kayıt" % len(rows))

    def _clear(self):
        self.date_var.set("")
        self.state_var.set("Tümü")
        self._fill()

    def _export(self):
        rows = self._rows()
        if not rows:
            messagebox.showinfo("Geçmiş", "Aktarılacak kayıt yok.", parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self, title="Geçmişi Kaydet", defaultextension=".csv",
            initialfile=report.default_report_name(),
            filetypes=[("CSV", "*.csv"), ("Metin", "*.txt")])
        if not path:
            return
        try:
            report.write_report(path, rows)
            messagebox.showinfo("Geçmiş", "Kaydedildi:\n%s" % path, parent=self)
        except Exception as exc:
            messagebox.showerror("Hata", "Kaydedilemedi: %s" % exc, parent=self)
