import json
import time
from pathlib import Path

from core import auth, browser, config, selectors as selectors_mod
from core.bot import PlaygroundBot

settings = config.load_settings()
driver = browser.launch_chrome(settings)
try:
    ok = auth.ensure_authenticated(driver, settings, email=settings.get("email", ""), password="", log=print)
    print("authenticated:", ok)
    if not ok:
        input("Complete login, then press Enter...")
    bot = PlaygroundBot(driver, settings, selectors_mod.load_selectors(settings), log=print)
    known = bot.collect_video_srcs()
    bot.submit("A fox running through dawn mist", startframe=None)

    def snapshot(tag):
        data = driver.execute_script(
            """
            const media = [];
            document.querySelectorAll('video, source, img, a').forEach(el => {
                for (const a of ['src','currentSrc','data-src','poster','href']) {
                    const v = el.getAttribute(a) || (a==='currentSrc' ? el.currentSrc : null);
                    if (v && v.startsWith('http')) media.push({tag: el.tagName, attr: a, url: v.slice(0,160)});
                }
            });
            const perf = [];
            try {
                performance.getEntriesByType('resource').forEach(e => {
                    if (/\.(mp4|webm|m3u8|mov)/i.test(e.name) || /video|cdn|media/i.test(e.name)) perf.push(e.name.slice(0,200));
                });
            } catch(e){}
            const txt = (document.body.innerText || '').trim().slice(0, 2000);
            return {media, perf, txt};
            """
        )
        print(f"--- snapshot {tag} ---")
        print("media:", json.dumps(data["media"], indent=1)[:2000])
        print("perf:", json.dumps(data["perf"], indent=1)[:2000])
        print("txt:", data["txt"][:800])
        print("---")

    for t in range(0, 13):
        time.sleep(10)
        snapshot(f"t+{t*10}s")
finally:
    driver.quit()