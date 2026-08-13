import sys
sys.path.insert(0, r"E:\Web App\Flux-Automation-")

from core import auth, browser, config, profiles

settings = config.load_settings()
profile = profiles.get_profile("main") or {}
settings["cookie_string"] = profile.get("cookie_string", "")

driver = browser.launch_chrome(settings)
try:
    ok = auth.ensure_authenticated(driver, settings, cookie_string=settings["cookie_string"], log=print)
    print("auth:", ok)
    for key in ("sb-api-key", "supabase-key", "sb-url", "supabaseUrl", "SUPABASE_URL", "SUPABASE_KEY",
                "sb-refresh-token", "supabase.auth.token", "sb-auth-token"):
        try:
            v = driver.execute_script("return localStorage.getItem(arguments[0])", key)
            if v:
                print(key, "=", str(v)[:100])
        except Exception as ex:
            print("err", key, ex)
    perfs = driver.execute_script("return performance.getEntriesByType('resource').map(e => e.name)") or []
    sup = [p for p in perfs if "supabase" in p.lower() or "uhjidycotobjggwyjdww" in p]
    print("supabase perf:", sup[:5])
    # localStorage snapshot of auth domain
    ls = driver.execute_script(
        "const o = {}; for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); o[k] = localStorage.getItem(k).slice(0, 120); } return o;")
    for k, v in (ls or {}).items():
        print("LS:", k, "=", v)
finally:
    try:
        driver.quit()
    except Exception:
        pass