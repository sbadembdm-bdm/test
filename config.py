"""Uygulama ayarlarını config.json dosyasından yükler."""
import json
import os
from pathlib import Path

DEFAULT_CONFIG_NAME = "config.json"
EXAMPLE_CONFIG_NAME = "config.example.json"


def _base_dir() -> Path:
    import sys
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def config_path() -> Path:
    return _base_dir() / DEFAULT_CONFIG_NAME


def assets_dir() -> Path:
    """PyInstaller onefile içinde _MEIPASS, normalde proje kökündeki assets."""
    import sys
    if getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS) / "assets"
    return _base_dir() / "assets"


def load_config() -> dict:
    """config.json yoksa config.example.json içeriğiyle oluşturur ve döndürür."""
    path = config_path()
    if not path.exists():
        example = _base_dir() / EXAMPLE_CONFIG_NAME
        if not example.exists():
            import sys
            if getattr(sys, "_MEIPASS", None):
                example = Path(sys._MEIPASS) / EXAMPLE_CONFIG_NAME
        if example.exists():
            path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            raise FileNotFoundError(
                "config.json ve config.example.json bulunamadı."
            )
    with open(path, "r", encoding="utf-8-sig") as f:
        raw = f.read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        # Kullanıcı config.json'ı elle editleyip bozmuş olabilir. Bozuk dosyayı
        # yedekle, örnek dosyadan yeni bir config oluştur ve tekrar aç.
        import shutil
        import time as _t
        backup = path.with_suffix(".corrupt.%s.json" % int(_t.time()))
        try:
            shutil.copy2(path, backup)
        except Exception:
            pass
        example = _base_dir() / EXAMPLE_CONFIG_NAME
        if not example.exists():
            import sys
            if getattr(sys, "_MEIPASS", None):
                example = Path(sys._MEIPASS) / EXAMPLE_CONFIG_NAME
        if example.exists():
            path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
            with open(path, "r", encoding="utf-8-sig") as f:
                cfg = json.load(f)
            cfg["_config_recovered"] = {
                "reason": str(exc),
                "backup": str(backup),
            }
            return cfg
        raise


def save_config(cfg: dict) -> None:
    with open(config_path(), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def profile_names(cfg: dict):
    """Tanımlı profil adlarını döndürür (yoksa boş liste)."""
    return list((cfg.get("profiles") or {}).keys())


def resolve(cfg: dict, profile_name: str = None) -> dict:
    """
    Global ayarlar + seçili profilin ayarlarını birleştirip runner'ın beklediği
    düz (flat) config sözlüğünü döndürür. Profil yoksa eski format aynen döner.
    """
    profiles = cfg.get("profiles") or {}
    if not profiles:
        merged = dict(cfg)
        merged["_profile_name"] = "Varsayılan"
        return merged

    name = profile_name or cfg.get("active_profile") or next(iter(profiles))
    base = {k: v for k, v in cfg.items() if k not in ("profiles", "active_profile")}
    prof = profiles.get(name, {})
    merged = dict(base)
    merged.update(prof)
    merged["_profile_name"] = name
    return merged

