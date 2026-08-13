import json
import time
from pathlib import Path

PROFILES_FILE = Path(__file__).resolve().parent.parent / "profiles.json"


def parse_cookie_string(cookie_str):
    cookies = []
    for part in cookie_str.split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            if cookies:
                cookies[-1]["flags"].append(part.lower())
            continue
        key, value = part.split("=", 1)
        key, value = key.strip(), value.strip()
        low = key.lower()
        if low in ("path", "domain", "expires", "max-age", "samesite"):
            if cookies:
                cookies[-1][low] = value
            continue
        cookies.append({"name": key, "value": value, "flags": []})
    return cookies


def load_profiles():
    if PROFILES_FILE.exists():
        try:
            return json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_profiles(profiles):
    PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROFILES_FILE.write_text(json.dumps(profiles, indent=2, ensure_ascii=False), encoding="utf-8")


def get_profile(name):
    for p in load_profiles():
        if p["name"] == name:
            return p
    return None


def upsert_profile(name, cookie_string):
    profiles = load_profiles()
    entry = {"name": name, "cookie_string": cookie_string,
             "created": time.time(), "last_used": None}
    profiles = [p for p in profiles if p["name"] != name]
    profiles.append(entry)
    save_profiles(profiles)
    return entry


def delete_profile(name):
    save_profiles([p for p in load_profiles() if p["name"] != name])


def apply_cookie_string(driver, cookie_str):
    cookies = parse_cookie_string(cookie_str)
    if not cookies:
        return False
    driver.get("https://auth.bfl.ai")
    try:
        driver.execute_script("localStorage.clear(); return 1;")
    except Exception:
        pass
    for c in cookies:
        domain = c.get("domain") or ".bfl.ai"
        path = c.get("path") or "/"
        secure = "secure" in c["flags"]
        http_only = "httponly" in c["flags"]
        try:
            driver.add_cookie({
                "name": c["name"],
                "value": c["value"],
                "path": path,
                "domain": domain,
                "secure": secure,
                "httpOnly": http_only,
            })
        except Exception:
            continue
    return True