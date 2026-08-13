import sys
import time
from pathlib import Path

sys.path.insert(0, r"E:\Web App\Flux-Automation-")

from core import auth, browser, config, downloader, frame_extract, profiles
from core import selectors as selectors_mod
from core.bot import PlaygroundBot

settings = config.load_settings()
cookie_string = settings.get("cookie_string", "")
if not cookie_string:
    profile = profiles.get_profile("main")
    cookie_string = (profile or {}).get("cookie_string", "")
settings["cookie_string"] = cookie_string
driver = browser.launch_chrome(settings)
try:
    ok = auth.ensure_authenticated(
        driver, settings,
        email=settings.get("email", ""), password="",
        cookie_string=settings.get("cookie_string", ""),
        log=print,
    )
    print("authenticated:", ok)
    if not ok:
        print("AUTH_FAILED - need fresh cookie string")
        sys.exit(2)
    bot = PlaygroundBot(driver, settings, selectors_mod.load_selectors(settings), log=print)
    srcs = bot.generate_and_capture(
        "A cinematic behind-the-scenes shot on a massive film set at dusk. Warm tungsten lighting, smoke haze, camera slowly pushes in, photorealistic, 16:9.",
        startframe=None, timeout=600,
    )
    print("SRCS:", srcs)
    if srcs:
        out = Path("output/qa_t2v.mp4")
        cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
        downloader.download_video(srcs[0], out, cookies=cookies, driver=driver)
        print("downloaded:", out.exists(), out.stat().st_size if out.exists() else 0)
        link = Path("output/qa_t2v_link.png")
        frame_extract.extract_last_frame(out, link)
        print("frame:", link.exists())
        print("probe:", frame_extract.probe_video(out))
    else:
        print("NO OUTPUT CAPTURED")
except KeyboardInterrupt:
    print("interrupted")
finally:
    pass