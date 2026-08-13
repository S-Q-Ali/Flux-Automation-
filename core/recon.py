import json
import os
import time
from pathlib import Path

from selenium.webdriver.common.by import By

from . import auth
from . import browser
from . import config
from . import session_store

CANDIDATE_SELECTOR = (
    "textarea, input, button, [contenteditable='true'], [role='textbox'], "
    "[role='button'], [role='combobox'], [role='menuitem'], [role='tab'], "
    "[role='option'], [aria-label], [data-placeholder]"
)

LOGIN_WAIT = 300


def collect_candidates(driver):
    return driver.execute_script(
        """
        const els = document.querySelectorAll(arguments[0]);
        const out = [];
        for (const el of els) {
            const rect = el.getBoundingClientRect();
            if (rect.width < 8 || rect.height < 8) continue;
            const r = {};
            r.tag = el.tagName.toLowerCase();
            r.id = el.id || null;
            r.classes = typeof el.className === 'string' ? el.className : null;
            r.type = el.getAttribute('type') || null;
            r.placeholder = el.getAttribute('placeholder') || el.getAttribute('data-placeholder') || null;
            r.aria = el.getAttribute('aria-label') || el.getAttribute('aria-placeholder') || null;
            r.text = (el.innerText || '').trim().slice(0, 120) || null;
            r.value = (el.value || '').slice(0, 80) || null;
            r.contenteditable = el.getAttribute('contenteditable') || null;
            out.push(r);
        }
        return out;
        """,
        CANDIDATE_SELECTOR,
    )


def is_playground_page(driver):
    try:
        return "playground" in driver.current_url
    except Exception:
        return False


def dump_playground(driver, settings, log):
    driver.get(settings["playground_url"])
    log("Navigated to playground, waiting for the page to settle...")
    if not browser.wait_for(driver, 30, lambda: is_playground_page(driver)):
        log(f"URL now: {driver.current_url}")
    time.sleep(8)

    recon_dir = Path(__file__).resolve().parent.parent / "recon"
    recon_dir.mkdir(parents=True, exist_ok=True)

    html = driver.execute_script("return document.documentElement.outerHTML;")
    (recon_dir / "dom_dump.html").write_text(html, encoding="utf-8")

    candidates = collect_candidates(driver)
    (recon_dir / "candidates.json").write_text(
        json.dumps(candidates, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    videos = driver.find_elements(By.TAG_NAME, "video")
    video_info = [v.get_attribute("src") for v in videos if v.get_attribute("src")]
    (recon_dir / "videos.json").write_text(
        json.dumps(video_info, indent=2), encoding="utf-8"
    )

    files = [f for f in driver.find_elements(By.CSS_SELECTOR, "input[type='file']")]
    file_info = []
    for f in files:
        try:
            file_info.append({
                "id": f.get_attribute("id"),
                "accept": f.get_attribute("accept"),
                "classes": f.get_attribute("class"),
                "visible": f.is_displayed(),
            })
        except Exception:
            continue
    (recon_dir / "file_inputs.json").write_text(
        json.dumps(file_info, indent=2), encoding="utf-8"
    )

    log(f"DOM dumped: {len(html)} chars, {len(candidates)} interactive elements, "
        f"{len(video_info)} videos, {len(file_info)} file inputs")


def main():
    settings = config.load_settings()
    settings["email"] = os.environ.get("BFL_EMAIL", settings.get("email", ""))
    password = os.environ.get("BFL_PASSWORD", "")

    def log(m):
        print(m, flush=True)

    driver = browser.launch_chrome(settings)
    try:
        if not auth.ensure_authenticated(
            driver, settings, email=settings["email"], password=password, log=log
        ):
            log("Not on dashboard yet. Complete login in the browser window now.")
            if not browser.wait_for(driver, LOGIN_WAIT, lambda: auth.on_dashboard(driver)):
                log("Still not on dashboard after wait. Dumping whatever loaded.")
        dump_playground(driver, settings, log)
    finally:
        try:
            session_store.save_session(driver, settings)
            log("Session saved to session.json")
        except Exception:
            pass
        driver.quit()
    log("Recon done. Review recon/*.json to finalize selectors.")


if __name__ == "__main__":
    main()