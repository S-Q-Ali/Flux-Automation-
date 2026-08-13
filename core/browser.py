import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from . import config


def launch_chrome(settings, headless=None):
    headless = settings.get("headless", False) if headless is None else headless
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

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": (
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )
        },
    )
    return driver


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