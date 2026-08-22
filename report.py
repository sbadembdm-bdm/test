"""İzleme olay geçmişini tarih/saatli rapor dosyasına (CSV veya TXT) aktarır."""
import csv
from datetime import datetime
from pathlib import Path


def write_report(path, history):
    """
    history: [(zaman_str, state, msg), ...]
    Uzantı .csv ise CSV, aksi halde düz metin yazar. Yazılan dosya yolunu döndürür.
    """
    path = str(path)
    if path.lower().endswith(".csv"):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["Zaman", "Durum", "Mesaj"])
            for row in history:
                w.writerow(list(row))
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write("BDM UYAP GİRİŞ - İzleme Raporu\n")
            f.write("Oluşturulma: %s\n" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            f.write("=" * 50 + "\n")
            for ts, state, msg in history:
                f.write("%s  [%s]  %s\n" % (ts, state, msg))
    return path


def default_report_name():
    return "uyap_rapor_%s.csv" % datetime.now().strftime("%Y%m%d_%H%M%S")


def resolve_report_path(p):
    """Boşsa varsayılan dosya adı; .csv/.txt ise aynen; aksi halde dizin kabul edilir."""
    p = (p or "").strip()
    if not p:
        return default_report_name()
    low = p.lower()
    if low.endswith(".csv") or low.endswith(".txt"):
        return p
    Path(p).mkdir(parents=True, exist_ok=True)
    return str(Path(p) / default_report_name())
