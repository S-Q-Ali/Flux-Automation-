import atexit
import time
import urllib.request

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from . import config

_DRIVER = None
_DEBUG_PORT = 9333


def _is_browser_up(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2):
            return True
    except Exception:
        return False


def _base_options(settings, headless):
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,800")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-infobars")
    options.add_argument("--lang=en-US")
    options.add_argument(f"--user-agent={config.credible_user_agent()}")
    options.add_argument(f"--user-data-dir={settings['chrome_profile']}")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "download.default_directory": settings["output_dir"],
    }
    options.add_experimental_option("prefs", prefs)
    return options


def _hide_webdriver(driver):
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"},
        )
    except Exception:
        pass


def _attach(settings, headless):
    options = _base_options(settings, headless)
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{_DEBUG_PORT}")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    _hide_webdriver(driver)
    return driver


def _fresh(settings, headless):
    options = _base_options(settings, headless)
    options.add_argument(f"--remote-debugging-port={_DEBUG_PORT}")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    _hide_webdriver(driver)
    return driver


def launch_chrome(settings, headless=None):
    """Reuse the SAME Chrome window across runs (SeedX-style).

    If a browser is already running on the debug port, attach to it so the
    login/session (and the Supabase auto-refreshing Bearer) stays alive.
    Only launches a fresh window on the first call or if the old one died.
    """
    global _DRIVER
    headless = settings.get("headless", False) if headless is None else headless

    if _DRIVER is not None:
        try:
            _DRIVER.current_url  # still alive?
            return _DRIVER
        except Exception:
            _DRIVER = None

    if _is_browser_up(_DEBUG_PORT):
        try:
            _DRIVER = _attach(settings, headless)
            print("Browser: attached to existing window")
            return _DRIVER
        except Exception as exc:
            print(f"Browser attach failed: {exc}")
            _DRIVER = None

    _DRIVER = _fresh(settings, headless)
    print("Browser: launched a new window")
    return _DRIVER


def close_browser():
    """Explicitly close the persistent browser. Usually not called - we keep it alive."""
    global _DRIVER
    if _DRIVER is not None:
        try:
            _DRIVER.quit()
        except Exception:
            pass
        _DRIVER = None


def wait_for(driver, timeout, predicate, interval=0.5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            value = predicate()
            if value:
                return value
        except Exception:
            pass
        time.sleep(interval)
    return None


def fetch_bytes_with_browser(driver, url):
    script = (
        "const r = await fetch(arguments[0], {credentials: 'include'});"
        "const b = await r.blob();"
        "const buf = await b.arrayBuffer();"
        "const bytes = new Uint8Array(buf);"
        "let binary = '';"
        "for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);"
        "return btoa(binary);"
    )
    return driver.execute_async_script(script, url)


atexit.register(close_browser)