import time

from selenium.webdriver.common.by import By

from . import browser
from . import session_store

AUTH_URL = "https://auth.bfl.ai/?redirect_uri=https://dashboard.bfl.ai"
DASHBOARD = "https://dashboard.bfl.ai"


def on_dashboard(driver):
    try:
        return DASHBOARD in driver.current_url
    except Exception:
        return False


def login_with_credentials(driver, email=None, password=None):
    driver.get(AUTH_URL)
    time.sleep(2)

    email_input = browser.wait_for(
        driver,
        15,
        lambda: driver.find_elements(By.CSS_SELECTOR, "input[type='email'], input[name='email'], input[autocomplete='email']")
        or driver.find_elements(By.CSS_SELECTOR, "input[type='text']"),
    )
    if not email_input:
        return False
    email_input[0].clear()
    email_input[0].send_keys(email)

    password_input = browser.wait_for(
        driver,
        10,
        lambda: driver.find_elements(By.CSS_SELECTOR, "input[type='password']"),
    )
    if not password_input:
        return False
    password_input[0].send_keys(password)

    buttons = driver.find_elements(By.CSS_SELECTOR, "button[type='submit'], button")
    submit = None
    for btn in buttons:
        label = (btn.text or "").lower()
        if "sign in" in label or "log in" in label or "continue" in label:
            submit = btn
            break
    if submit is None and buttons:
        submit = buttons[0]
    if submit is None:
        return False
    submit.click()

    return browser.wait_for(driver, 12, on_dashboard)


def ensure_authenticated(driver, settings, email=None, password=None, cookie_string=None, log=lambda m: None):
    if browser.wait_for(driver, 8, lambda: on_dashboard(driver)):
        return True

    if session_store.load_session(driver, settings):
        driver.get(settings["playground_url"])
        if browser.wait_for(driver, 12, lambda: on_dashboard(driver)):
            return True

    if cookie_string:
        from . import profiles

        log("Applying profile cookies...")
        profiles.apply_cookie_string(driver, cookie_string)
        driver.get(settings["playground_url"])
        if browser.wait_for(driver, 12, lambda: on_dashboard(driver)):
            session_store.save_session(driver, settings)
            log("Session established from profile cookies")
            return True
        log("Profile cookies did not establish a session.")

    if not email or not password:
        return False

    if login_with_credentials(driver, email, password):
        log("Login submitted")
    else:
        log("Automated login incomplete - finish signing in manually in the browser window")

    if browser.wait_for(driver, 90, on_dashboard):
        session_store.save_session(driver, settings)
        log("Session saved")
        driver.get(settings["playground_url"])
        return True

    if on_dashboard(driver):
        session_store.save_session(driver, settings)
        return True
    return False