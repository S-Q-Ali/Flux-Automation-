import time
from pathlib import Path

from core import auth, browser, config, downloader, frame_extract
from core import selectors as selectors_mod
from core.bot import PlaygroundBot

settings = config.load_settings()
driver = browser.launch_chrome(settings)
try:
    ok = auth.ensure_authenticated(driver, settings, email=settings.get("email", ""), password="", log=print)
    print("authenticated:", ok)
    if not ok:
        input("Complete login in the browser window, then press Enter to continue...")
        ok = True
    bot = PlaygroundBot(driver, settings, selectors_mod.load_selectors(settings), log=print)
    srcs = bot.generate_and_capture("A fox running through dawn mist", startframe=None, timeout=600)
    print("SRCS:", srcs)
    if srcs:
        out = Path("output/qa_test.mp4")
        cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
        downloader.download_video(srcs[0], out, cookies=cookies, driver=driver)
        print("downloaded:", out.exists(), out.stat().st_size if out.exists() else 0)
        link = Path("output/qa_link.png")
        frame_extract.extract_last_frame(out, link)
        print("frame:", link.exists())
        print("probe:", frame_extract.probe_video(out))
    else:
        print("NO OUTPUT CAPTURED")
finally:
    driver.quit()