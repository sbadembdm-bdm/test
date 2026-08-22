"""Zamanlı görev yönetim penceresi: config.json'daki 'scheduled_tasks' düzenlenir."""
import copy
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from . import theme

DAY_NAMES = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
ACTIONS = ["goto", "wait", "click", "type", "screenshot"]
TIME_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")

TEMPLATES = {
    "Sabah iş listesi + rapor": {
        "name": "Sabah iş listesi", "time": "09:00", "days": [1, 2, 3, 4, 5],
        "tasks": [
            {"action": "goto", "url": "https://avukat.uyap.gov.tr/main/#/is-listesi"},
            {"action": "wait", "seconds": 3},
        ],
        "export_report": True, "report_path": ""},
    "Dosya sorgulama": {
        "name": "Dosya sorgulama", "time": "10:00", "days": [1, 2, 3, 4, 5],
        "tasks": [
            {"action": "goto", "url": "https://avukat.uyap.gov.tr/main/#/dosya-sorgulama"},
            {"action": "wait", "seconds": 2},
        ],
        "export_report": False, "report_path": ""},
    "Gelen evrak kontrolü": {
        "name": "Gelen evrak", "time": "11:00", "days": [1, 2, 3, 4, 5],
        "tasks": [
            {"action": "goto", "url": "https://avukat.uyap.gov.tr/main/#/evrak/gelen"},
            {"action": "wait", "seconds": 2},
        ],
        "export_report": False, "report_path": ""},
    "Derdest dosyalar": {
        "name": "Derdest dosyalar", "time": "14:00", "days": [1, 2, 3, 4, 5],
        "tasks": [
            {"action": "goto", "url": "https://avukat.uyap.gov.tr/main/#/dosyalarim/derdest"},
            {"action": "wait", "seconds": 3},
        ],
        "export_report": False, "report_path": ""},
    "Akşam durum raporu": {
        "name": "Akşam durum raporu", "time": "18:00", "days": [1, 2, 3, 4, 5],
        "tasks": [], "export_report": True, "report_path": ""},
}


def _step_detail(step):
    return ", ".join("%s=%s" % (k, v) for k, v in step.items() if k != "action")


class StepDialog(tk.Toplevel):
    """Tek bir görev adımı (goto/wait/click/type/screenshot) ekleme-düzenleme."""

    FIELDS = {
        "goto": [("url", "Adres (URL)")],
        "wait": [("seconds", "Süre (saniye)")],
        "click": [("selector", "Selector (CSS/XPath)")],
        "type": [("selector", "Selector (CSS/XPath)"), ("text", "Yazılacak metin")],
        "screenshot": [("path", "Dosya yolu (örn. C:\\raporlar\\ekran.png)")],
    }

    def __init__(self, parent, step=None):
        super().__init__(parent)
        self.title("Görev Adımı")
        self.configure(bg=theme.BG)
        self.resizable(False, False)
        self.result = None
        self._initial = step or {}
        self.action_var = tk.StringVar(value=self._initial.get("action", "goto"))

        ttk.Label(self, text="İşlem").grid(row=0, column=0, sticky="w", padx=10, pady=8)
        cb = ttk.Combobox(self, textvariable=self.action_var, values=ACTIONS,
                          state="readonly", width=14)
        cb.grid(row=0, column=1, sticky="w", padx=10)
        cb.bind("<<ComboboxSelected>>", lambda e: self._render_fields())

        self.field_frame = ttk.Frame(self)
        self.field_frame.grid(row=1, column=0, columnspan=2, sticky="we", padx=10)
        self.vars = {}
        self._render_fields()

        btns = ttk.Frame(self)
        btns.grid(row=2, column=0, columnspan=2, pady=10)
        ttk.Button(btns, text="Tamam", command=self._ok).pack(side="left", padx=6)
        ttk.Button(btns, text="İptal", command=self.destroy).pack(side="left")
        self.transient(parent)
        self.grab_set()

    def _render_fields(self):
        for w in self.field_frame.winfo_children():
            w.destroy()
        self.vars = {}
        for i, (key, label) in enumerate(self.FIELDS[self.action_var.get()]):
            ttk.Label(self.field_frame, text=label).grid(row=i, column=0, sticky="w", pady=4)
            var = tk.StringVar(value=str(self._initial.get(key, "")))
            ttk.Entry(self.field_frame, textvariable=var, width=46).grid(
                row=i, column=1, pady=4, padx=6)
            self.vars[key] = var

    def _ok(self):
        step = {"action": self.action_var.get()}
        for key, var in self.vars.items():
            val = var.get().strip()
            if not val:
                messagebox.showwarning("Eksik", "Tüm alanları doldurun.", parent=self)
                return
            if key == "seconds":
                try:
                    val = int(val)
                except ValueError:
                    messagebox.showwarning("Hatalı", "Süre sayı olmalı (örn. 3).", parent=self)
                    return
            step[key] = val
        self.result = step
        self.destroy()


class TaskManagerWindow(tk.Toplevel):
    """Zamanlı görevleri listeler; ekleme/silme/düzenleme yapıp on_save ile geri verir."""

    def __init__(self, parent, config, on_save):
        super().__init__(parent)
        self.title("Zamanlı Görevler")
        self.configure(bg=theme.BG)
        self.geometry("900x560")
        self.on_save = on_save
        self.tasks = copy.deepcopy(config.get("scheduled_tasks") or [])
        self.current = None
        self._build()
        self._refresh_list()
        if self.tasks:
            self.task_lb.selection_set(0)
            self._on_select()
        self.transient(parent)
        self.grab_set()

    # ---------- UI ----------
    def _build(self):
        left = ttk.Frame(self)
        left.pack(side="left", fill="y", padx=10, pady=10)
        ttk.Label(left, text="Görevler").pack(anchor="w")
        self.task_lb = tk.Listbox(left, width=30, height=20, exportselection=False)
        theme.style_listbox(self.task_lb)
        self.task_lb.pack(fill="y", expand=True, pady=4)
        self.task_lb.bind("<<ListboxSelect>>", lambda e: self._on_select())
        lb_btns = ttk.Frame(left)
        lb_btns.pack(fill="x")
        ttk.Button(lb_btns, text="Yeni Görev", command=self._new_task).pack(side="left")
        ttk.Button(lb_btns, text="Görevi Sil", command=self._delete_task).pack(side="left", padx=6)
        ttk.Button(left, text="Şablondan Ekle ▾",
                   command=self._template_menu).pack(fill="x", pady=(6, 0))

        right = ttk.Frame(self)
        right.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=10)
        pad = {"padx": 4, "pady": 4}

        ttk.Label(right, text="Görev Adı").grid(row=0, column=0, sticky="w", **pad)
        self.name_var = tk.StringVar()
        ttk.Entry(right, textvariable=self.name_var, width=36).grid(row=0, column=1, sticky="w", **pad)

        ttk.Label(right, text="Saat (SS:DD)").grid(row=1, column=0, sticky="w", **pad)
        self.time_var = tk.StringVar()
        ttk.Entry(right, textvariable=self.time_var, width=8).grid(row=1, column=1, sticky="w", **pad)

        ttk.Label(right, text="Günler").grid(row=2, column=0, sticky="w", **pad)
        days = ttk.Frame(right)
        days.grid(row=2, column=1, sticky="w", **pad)
        self.day_vars = []
        for i, d in enumerate(DAY_NAMES):
            var = tk.BooleanVar(value=i < 5)
            ttk.Checkbutton(days, text=d, variable=var).pack(side="left")
            self.day_vars.append(var)

        rrow = ttk.Frame(right)
        rrow.grid(row=3, column=1, sticky="w", **pad)
        self.export_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(rrow, text="Rapor üret:", variable=self.export_var).pack(side="left")
        self.report_var = tk.StringVar()
        ttk.Entry(rrow, textvariable=self.report_var, width=28).pack(side="left", padx=4)
        ttk.Button(rrow, text="Gözat", width=6, command=self._browse_report).pack(side="left")

        ttk.Label(right, text="Adımlar").grid(row=4, column=0, sticky="nw", **pad)
        tree_frame = ttk.Frame(right)
        tree_frame.grid(row=4, column=1, sticky="we", **pad)
        self.tree = ttk.Treeview(tree_frame, columns=("islem", "detay"),
                                 show="headings", height=9)
        self.tree.heading("islem", text="İşlem")
        self.tree.heading("detay", text="Detay")
        self.tree.column("islem", width=90, stretch=False)
        self.tree.column("detay", width=380)
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        sb.pack(side="left", fill="y")
        self.tree.configure(yscrollcommand=sb.set)

        srow = ttk.Frame(right)
        srow.grid(row=5, column=1, sticky="w", **pad)
        ttk.Button(srow, text="Adım Ekle", command=self._add_step).pack(side="left")
        ttk.Button(srow, text="Düzenle", command=self._edit_step).pack(side="left", padx=4)
        ttk.Button(srow, text="Sil", command=self._del_step).pack(side="left")
        ttk.Button(srow, text="↑", width=3, command=lambda: self._move_step(-1)).pack(side="left", padx=(10, 2))
        ttk.Button(srow, text="↓", width=3, command=lambda: self._move_step(1)).pack(side="left")

        brow = ttk.Frame(right)
        brow.grid(row=6, column=1, sticky="e", pady=12)
        ttk.Button(brow, text="Kaydet ve Kapat", command=self._save).pack(side="left", padx=6)
        ttk.Button(brow, text="İptal", command=self.destroy).pack(side="left")

    # ---------- liste ----------
    def _label(self, t):
        return "%s  (%s)" % (t.get("name") or "İsimsiz", t.get("time") or "--:--")

    def _refresh_list(self):
        self.task_lb.delete(0, "end")
        for t in self.tasks:
            self.task_lb.insert("end", self._label(t))

    def _on_select(self):
        sel = self.task_lb.curselection()
        if not sel:
            return
        self._store_form()
        self.current = sel[0]
        self._load_form(self.tasks[self.current])

    def _new_task(self):
        self._store_form()
        self.tasks.append({"name": "Yeni Görev", "time": "09:00",
                           "days": [1, 2, 3, 4, 5], "tasks": [],
                           "export_report": False, "report_path": ""})
        self._refresh_list()
        idx = len(self.tasks) - 1
        self.task_lb.selection_clear(0, "end")
        self.task_lb.selection_set(idx)
        self.current = idx
        self._load_form(self.tasks[idx])

    def _template_menu(self):
        menu = tk.Menu(self, tearoff=0, bg=theme.FIELD, fg=theme.TEXT,
                       activebackground=theme.GOLD, activeforeground=theme.GOLD_TEXT,
                       relief="flat", font=theme.FONT_SMALL)
        for name in TEMPLATES:
            menu.add_command(label=name, command=lambda n=name: self._add_template(n))
        menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())

    def _add_template(self, name):
        self._store_form()
        self.tasks.append(copy.deepcopy(TEMPLATES[name]))
        self._refresh_list()
        idx = len(self.tasks) - 1
        self.task_lb.selection_clear(0, "end")
        self.task_lb.selection_set(idx)
        self.current = idx
        self._load_form(self.tasks[idx])

    def _delete_task(self):
        if self.current is None:
            return
        if not messagebox.askyesno("Sil", "Seçili görev silinsin mi?", parent=self):
            return
        del self.tasks[self.current]
        self.current = None
        self._refresh_list()
        self._load_form({})

    # ---------- form ----------
    def _load_form(self, t):
        self.name_var.set(t.get("name", ""))
        self.time_var.set(t.get("time", ""))
        days = t.get("days") or []
        for i, var in enumerate(self.day_vars):
            var.set((i + 1) in days)
        self.export_var.set(bool(t.get("export_report")))
        self.report_var.set(t.get("report_path", ""))
        self.tree.delete(*self.tree.get_children())
        for step in t.get("tasks", []):
            self.tree.insert("", "end", values=(step.get("action", "?"), _step_detail(step)))
        self._steps = copy.deepcopy(t.get("tasks", []))

    def _store_form(self):
        if self.current is None or self.current >= len(self.tasks):
            return
        t = self.tasks[self.current]
        t["name"] = self.name_var.get().strip() or "İsimsiz"
        t["time"] = self.time_var.get().strip()
        t["days"] = [i + 1 for i, var in enumerate(self.day_vars) if var.get()]
        t["export_report"] = self.export_var.get()
        t["report_path"] = self.report_var.get().strip()
        t["tasks"] = copy.deepcopy(getattr(self, "_steps", []))
        self.task_lb.delete(self.current)
        self.task_lb.insert(self.current, self._label(t))
        self.task_lb.selection_set(self.current)

    def _browse_report(self):
        path = filedialog.asksaveasfilename(
            parent=self, title="Rapor Dosyası", defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Metin", "*.txt")])
        if path:
            self.report_var.set(path)

    # ---------- adımlar ----------
    def _sel_step_index(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.index(sel[0])

    def _redraw_steps(self, select=None):
        self.tree.delete(*self.tree.get_children())
        for step in self._steps:
            self.tree.insert("", "end", values=(step.get("action", "?"), _step_detail(step)))
        if select is not None:
            kids = self.tree.get_children()
            if 0 <= select < len(kids):
                self.tree.selection_set(kids[select])

    def _add_step(self):
        if self.current is None:
            messagebox.showinfo("Görev", "Önce soldan bir görev seçin veya oluşturun.", parent=self)
            return
        dlg = StepDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            self._steps.append(dlg.result)
            self._redraw_steps(len(self._steps) - 1)

    def _edit_step(self):
        idx = self._sel_step_index()
        if idx is None:
            return
        dlg = StepDialog(self, self._steps[idx])
        self.wait_window(dlg)
        if dlg.result:
            self._steps[idx] = dlg.result
            self._redraw_steps(idx)

    def _del_step(self):
        idx = self._sel_step_index()
        if idx is None:
            return
        del self._steps[idx]
        self._redraw_steps()

    def _move_step(self, delta):
        idx = self._sel_step_index()
        if idx is None:
            return
        new = idx + delta
        if not (0 <= new < len(self._steps)):
            return
        self._steps[idx], self._steps[new] = self._steps[new], self._steps[idx]
        self._redraw_steps(new)

    # ---------- kayıt ----------
    def _save(self):
        self._store_form()
        for t in self.tasks:
            if not TIME_RE.match(t.get("time", "")):
                messagebox.showwarning(
                    "Hatalı Saat",
                    "'%s' görevinin saati geçersiz. SS:DD biçiminde girin (örn. 09:30)." % t["name"],
                    parent=self)
                return
            if not t.get("days"):
                messagebox.showwarning(
                    "Gün Seçilmedi",
                    "'%s' görevi için en az bir gün seçin." % t["name"], parent=self)
                return
        self.on_save(self.tasks)
        self.destroy()
