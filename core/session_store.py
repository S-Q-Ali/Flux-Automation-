import json
import time
from pathlib import Path


def save_session(driver, settings):
    base = Path(settings["session_file"])
    base.parent.mkdir(parents=True, exist_ok=True)
    cookies = [c for c in driver.get_cookies() if c.get("domain") and "bfl.ai" in c["domain"]]

    origins = {
        "https://auth.bfl.ai": "auth.bfl.ai",
        "https://dashboard.bfl.ai": "dashboard.bfl.ai",
        "https://bfl.ai": "bfl.ai",
    }
    local_storage = {}
    for origin in origins:
        try:
            driver.get(origin)
            time.sleep(0.3)
            data = driver.execute_script(
                "const o = {}; for (let i=0;i<localStorage.length;i++){const k=localStorage.key(i);o[k]=localStorage.getItem(k);} return o;"
            )
            if data:
                local_storage[origin] = data
        except Exception:
            continue

    payload = {"cookies": cookies, "local_storage": local_storage}
    base.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def load_session(driver, settings):
    base = Path(settings["session_file"])
    if not base.exists():
        return False
    try:
        payload = json.loads(base.read_text(encoding="utf-8"))
    except Exception:
        return False

    cookies = payload.get("cookies", [])
    if cookies:
        driver.get("https://auth.bfl.ai")
        try:
            driver.execute_script("localStorage.clear(); return 1;")
        except Exception:
            pass
        for c in cookies:
            try:
                driver.add_cookie(
                    {
                        "name": c["name"],
                        "value": c["value"],
                        "path": c.get("path", "/"),
                        "domain": c["domain"],
                        "secure": bool(c.get("secure", True)),
                        "httpOnly": bool(c.get("httpOnly", False)),
                    }
                )
            except Exception:
                pass

    for origin, items in (payload.get("local_storage") or {}).items():
        try:
            driver.get(origin)
            time.sleep(0.3)
            for k, v in items.items():
                try:
                    driver.execute_script(
                        "localStorage.setItem(arguments[0], arguments[1]);", k, v
                    )
                except Exception:
                    pass
        except Exception:
            pass

    return bool(cookies or (payload.get("local_storage") or {}))


def save_credentials(email, password):
    try:
        import keyring

        keyring.set_password("bfl_flux_automation", "password", password)
    except Exception:
        pass
    return email


def load_credentials():
    email = None
    password = None
    try:
        import keyring

        password = keyring.get_password("bfl_flux_automation", "password")
    except Exception:
        password = None
    return email, password