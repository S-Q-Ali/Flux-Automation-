import re
from pathlib import Path

import requests


def sanitize(name):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")


def download_video(url, out_path, cookies=None, driver=None):
    if cookies is None:
        cookies = {}
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://dashboard.bfl.ai/",
        }
        with requests.get(url, headers=headers, cookies=cookies, stream=True, timeout=60) as r:
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "wb") as fh:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if chunk:
                        fh.write(chunk)
        return out_path
    except Exception:
        if driver is not None:
            from . import browser

            data = browser.fetch_bytes_with_browser(driver, url)
            import base64

            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "wb") as fh:
                fh.write(base64.b64decode(data))
            return out_path
        raise