import time
from pathlib import Path

from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from . import browser


class PlaygroundBot:
    def __init__(self, driver, settings, selectors, log=lambda m: None):
        self.driver = driver
        self.settings = settings
        self.selectors = selectors
        self.log = log

    def visible(self, element):
        try:
            return element.is_displayed()
        except Exception:
            return False

    def first_visible(self, elements):
        for el in elements:
            if self.visible(el):
                return el
        return None

    def on_playground(self):
        try:
            return "playground" in self.driver.current_url
        except Exception:
            return False

    def goto_playground(self):
        if not self.on_playground():
            self.driver.get(self.settings["playground_url"])
        browser.wait_for(self.driver, 20, lambda: self.on_playground())

    def find_prompt_input(self):
        for selector in self.selectors["prompt_input"]:
            try:
                el = self.first_visible(self.driver.find_elements(By.CSS_SELECTOR, selector))
                if el is not None:
                    return el
            except Exception:
                continue
        try:
            els = self.driver.find_elements(By.CSS_SELECTOR, "textarea, [contenteditable='true'], [role='textbox']")
            return self.first_visible(els)
        except Exception:
            return None

    def find_generate_button(self):
        texts = [t.lower() for t in self.selectors["generate_texts"]]
        for selector in self.selectors["generate_button"]:
            try:
                for el in self.driver.find_elements(By.CSS_SELECTOR, selector):
                    if not self.visible(el):
                        continue
                    label = (el.text or "").strip().lower()
                    aria = ((el.get_attribute("aria-label") or "").strip().lower())
                    for t in texts:
                        if label == t or (t in label and len(label) <= 32) or (t in aria and len(aria) <= 32):
                            return el
            except Exception:
                continue
        return None

    def _value(self, element):
        try:
            return self.driver.execute_script("return arguments[0].value;", element) or ""
        except Exception:
            return ""

    def enter_prompt(self, prompt):
        target = self.find_prompt_input()
        if target is None:
            raise RuntimeError("prompt input not found - run recon to update selectors")
        target.click()
        try:
            target.clear()
            target.send_keys(prompt)
        except Exception as exc:
            raise RuntimeError(f"failed to enter prompt: {exc}")
        time.sleep(0.5)
        if self._value(target).strip() != prompt:
            try:
                self.driver.execute_script(
                    "const el = arguments[0];"
                    "const set = Object.getOwnPropertyDescriptor("
                    "window.HTMLTextAreaElement.prototype, 'value').set;"
                    "set.call(el, arguments[1]);"
                    "el.dispatchEvent(new Event('input', {bubbles:true}));"
                    "el.dispatchEvent(new Event('change', {bubbles:true}));",
                    target, prompt,
                )
                time.sleep(0.5)
            except Exception:
                pass
        entered = self._value(target)
        self.log(f"Prompt entered ({len(entered)} chars)")
        if entered.strip() != prompt:
            self.log("Warning: textarea value does not match prompt")
        return entered

    def upload_startframe(self, image_path, v2v=False):
        if v2v:
            selectors = self.selectors["start_video_upload"]
        else:
            selectors = self.selectors["start_frame_upload"]
        file_inputs = []
        for selector in selectors:
            try:
                file_inputs += self.driver.find_elements(By.CSS_SELECTOR, selector)
            except Exception:
                continue
        if not file_inputs:
            raise RuntimeError("no file upload input found - run recon to update selectors")
        self.driver.execute_script(
            "arguments[0].value = '';", file_inputs[0])
        file_inputs[0].send_keys(str(Path(image_path).resolve()))
        self.log("Startframe uploaded")
        time.sleep(3)

    def submit(self, prompt, startframe=None, v2v=False):
        self.goto_playground()
        if startframe:
            self.upload_startframe(startframe, v2v=v2v)
        self.enter_prompt(prompt)
        button = self.find_generate_button()
        if button is None:
            raise RuntimeError("generate button not found - run recon to update selectors")
        deadline = time.time() + 20
        while time.time() < deadline:
            if button.get_attribute("disabled") is None:
                break
            time.sleep(1)
        self.driver.execute_script("arguments[0].click();", button)
        self.log("Generation submitted")

    def collect_video_srcs(self):
        srcs = []
        try:
            for el in self.driver.find_elements(By.TAG_NAME, "video"):
                for attr in ("src", "data-src", "poster"):
                    src = el.get_attribute(attr)
                    if src and src.startswith("http") and src not in srcs:
                        srcs.append(src)
                for source in el.find_elements(By.TAG_NAME, "source"):
                    src = source.get_attribute("src")
                    if src and src.startswith("http") and src not in srcs:
                        srcs.append(src)
        except Exception:
            pass
        try:
            for el in self.driver.find_elements(By.CSS_SELECTOR, "a[href]"):
                href = el.get_attribute("href") or ""
                if href.startswith("http") and ".mp4" in href.lower():
                    if href not in srcs:
                        srcs.append(href)
        except Exception:
            pass
        try:
            perfs = self.driver.execute_script(
                "return performance.getEntriesByType('resource').map(e => e.name);") or []
            for name in perfs:
                if isinstance(name, str) and name.startswith("http"):
                    low = name.lower()
                    if ".mp4" in low or ".webm" in low or "/v1/generations/" in low or "/media/" in low:
                        if name not in srcs:
                            srcs.append(name)
        except Exception:
            pass
        return srcs

    def surface_errors(self):
        try:
            body = (self.driver.find_element(By.TAG_NAME, "body").text or "")
        except Exception:
            return
        lowered = body.lower()
        hits = []
        for token in self.selectors.get("error_texts", []):
            if token in lowered:
                hits.append(token)
        if hits:
            self.log("Possible error on page: " + ", ".join(hits))

    def wait_for_generation(self, known_srcs, timeout=600):
        self.log("Waiting for generation to complete...")
        deadline = time.time() + timeout
        while time.time() < deadline:
            srcs = self.collect_video_srcs()
            new = [s for s in srcs if s not in known_srcs]
            if new:
                self.log(f"New output found: {new[0][:80]}")
                return new
            self.surface_errors()
            time.sleep(3)
        return []

    def generate_and_capture(self, prompt, startframe=None, timeout=600, v2v=False):
        known = set(self.collect_video_srcs())
        self.submit(prompt, startframe, v2v=v2v)
        return self.wait_for_generation(known, timeout=timeout)