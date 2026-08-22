"""Masaüstü bildirimi (Windows toast). Kütüphane yoksa sessizce loglar."""

_NOTIFIER = None


def _get_notifier():
    global _NOTIFIER
    if _NOTIFIER is not None:
        return _NOTIFIER

    # 1) winotify (Windows 10/11 native toast)
    try:
        from winotify import Notification

        def _winotify(title, msg):
            Notification(app_id="BDM UYAP GİRİŞ", title=title, msg=msg).show()

        _NOTIFIER = _winotify
        return _NOTIFIER
    except Exception:
        pass

    # 2) plyer (çapraz platform)
    try:
        from plyer import notification as _pn

        def _plyer(title, msg):
            _pn.notify(title=title, message=msg, timeout=5)

        _NOTIFIER = _plyer
        return _NOTIFIER
    except Exception:
        pass

    _NOTIFIER = False  # kütüphane yok
    return _NOTIFIER


def notify(title, msg, enabled=True, logger=None):
    if not enabled:
        return
    fn = _get_notifier()
    if fn:
        try:
            fn(title, msg)
            return
        except Exception as exc:
            if logger:
                logger.warning("Bildirim gösterilemedi: %s", exc)
    if logger:
        logger.info("[BİLDİRİM] %s - %s", title, msg)
