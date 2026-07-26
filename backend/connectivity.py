import urllib.request

def is_online(timeout: int = 2) -> bool:
    """Simple check whether the server has internet connectivity.

    Attempts to open a lightweight HTTP URL (example.com). If the request
    succeeds, we assume internet access. This is used to gate online‑only
    features such as AI‑enhanced processing.
    """
    try:
        urllib.request.urlopen('http://example.com', timeout=timeout)
        return True
    except Exception:
        return False
