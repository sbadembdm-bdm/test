"""
Bilgisayarda takılı e-imza (akıllı kart) var mı? PKCS#11 üzerinden kontrol eder.

Dönüş:
  True  -> takılı token bulundu
  False -> kart okuyucuda token yok
  None  -> tespit yapılamadı (PyKCS11 yok ya da .dll bulunamadı) => "bilinmiyor"
"""
import os

# Windows'ta AKİS ve yaygın PKCS#11 kütüphaneleri
DEFAULT_CANDIDATES = [
    r"C:\Windows\System32\akisp11.dll",
    r"C:\Windows\System32\AkisP11.dll",
    r"C:\Windows\SysWOW64\akisp11.dll",
    r"C:\Program Files\AKIS\akisp11.dll",
    r"C:\Program Files (x86)\Akis\akisp11.dll",
]


def _resolve_lib(config):
    lib = (config.get("pkcs11_lib") or "").strip()
    if lib and os.path.exists(lib):
        return lib
    for cand in DEFAULT_CANDIDATES:
        if os.path.exists(cand):
            return cand
    return None


def _winscard_present(logger):
    """Windows yerleşik WinSCard API'si ile kart kontrolü (ek paket gerektirmez)."""
    import ctypes
    from ctypes import wintypes

    SCARD_SCOPE_USER = 0
    SCARD_STATE_UNAWARE = 0
    SCARD_STATE_PRESENT = 0x20

    class ReaderState(ctypes.Structure):
        _fields_ = [
            ("szReader", ctypes.c_wchar_p),
            ("pvUserData", ctypes.c_void_p),
            ("dwCurrentState", wintypes.DWORD),
            ("dwEventState", wintypes.DWORD),
            ("cbAtr", wintypes.DWORD),
            ("rgbAtr", ctypes.c_ubyte * 36),
        ]

    lib = ctypes.windll.winscard
    ctx = ctypes.c_void_p()
    if lib.SCardEstablishContext(SCARD_SCOPE_USER, None, None, ctypes.byref(ctx)) != 0:
        return None
    try:
        cch = wintypes.DWORD(0)
        rv = lib.SCardListReadersW(ctx, None, None, ctypes.byref(cch))
        if rv != 0 or cch.value <= 2:
            return False
        buf = (ctypes.c_wchar * cch.value)()
        if lib.SCardListReadersW(ctx, None, buf, ctypes.byref(cch)) != 0:
            return None
        readers = [r for r in "".join(buf).split("\x00") if r]
        if not readers:
            return False
        states = (ReaderState * len(readers))()
        for i, name in enumerate(readers):
            states[i].szReader = name
            states[i].dwCurrentState = SCARD_STATE_UNAWARE
        if lib.SCardGetStatusChangeW(ctx, 0, states, len(readers)) != 0:
            return None
        return any(s.dwEventState & SCARD_STATE_PRESENT for s in states)
    finally:
        lib.SCardReleaseContext(ctx)


def card_present(config, logger):
    if not config.get("card_detection", True):
        return None

    try:
        res = _winscard_present(logger)
        if res is not None:
            logger.info("Kart tespiti (WinSCard): %s",
                        "takılı kart bulundu" if res else "takılı kart YOK")
            return res
    except Exception:
        pass

    try:
        import PyKCS11
    except Exception:
        logger.info("PyKCS11 kurulu değil; kart tespiti atlanıyor (bilinmiyor).")
        return None

    lib = _resolve_lib(config)
    if not lib:
        logger.info("PKCS#11 kütüphanesi (akisp11.dll) bulunamadı; "
                    "kart tespiti atlanıyor. Gerekirse config'te 'pkcs11_lib' verin.")
        return None

    try:
        pk = PyKCS11.PyKCS11Lib()
        pk.load(lib)
        slots = pk.getSlotList(tokenPresent=True)
        present = len(slots) > 0
        logger.info("Kart tespiti (%s): %s", lib,
                    "takılı kart bulundu" if present else "takılı kart YOK")
        return present
    except Exception as exc:
        logger.warning("Kart tespitinde hata (%s): %s", lib, exc)
        return None
