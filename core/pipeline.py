import json
import time
from pathlib import Path

from . import auth
from . import audio as audio_mod
from . import bot as bot_mod
from . import browser
from . import config
from . import downloader
from . import frame_extract
from .history import SessionHistory
from . import normalize as normalize_mod
from . import render as render_mod
from . import selectors as selectors_mod

STATUS = {"pending": "pending", "generating": "generating", "downloaded": "downloaded",
          "done": "done", "error": "error"}


class MoviePipeline:
    def __init__(self, prompts, settings, email="", password="", cookie_string="",
                 on_stage=None, on_progress=None, on_message=None, on_finished=None):
        self.prompts = [p for p in (p or []) if p and p.strip()]
        self.settings = settings
        self.email = email
        self.password = password
        self.cookie_string = cookie_string
        self.on_stage = on_stage or (lambda m: None)
        self.on_progress = on_progress or (lambda a, b: None)
        self.on_message = on_message or (lambda m: None)
        self.on_finished = on_finished or (lambda r: None)
        self._stop = False
        self._driver = None
        self._summary = {}
        self.history = SessionHistory()
        self.history.record("pipeline_start", scenes=len(self.prompts), settings={k: v for k, v in settings.items() if k != "password"})

    def request_stop(self):
        self._stop = True

    def _save_state(self, state):
        state["updated"] = time.time()
        Path(self.settings["state_file"]).write_text(
            json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load_state(self):
        path = Path(self.settings["state_file"])
        n = len(self.prompts)
        if path.exists():
            try:
                state = json.loads(path.read_text(encoding="utf-8"))
                if len(state.get("scenes", [])) == n:
                    return state
            except Exception:
                pass
        scenes = [{"index": i + 1, "prompt": self.prompts[i], "status": STATUS["pending"],
                   "clip": None, "link": None, "error": None, "attempts": 0} for i in range(n)]
        return {"scenes": scenes, "updated": time.time()}

    def _first_incomplete(self, state, dirs):
        for scene in state["scenes"]:
            if scene["status"] == STATUS["done"]:
                clip = scene.get("clip")
                link = scene.get("link")
                if clip and link and Path(clip).exists() and Path(link).exists():
                    continue
            return scene["index"] - 1
        return len(state["scenes"])

    def run(self):
        self.on_stage("initializing")
        n = len(self.prompts)
        if n == 0:
            self.on_message("No prompts loaded.")
            self.on_finished({"ok": False, "error": "no prompts"})
            return
        dirs = config.ensure_dirs(self.settings)
        state = self._load_state()
        selectors = selectors_mod.load_selectors(self.settings)

        self._driver = browser.launch_chrome(self.settings)
        try:
            ok = auth.ensure_authenticated(
                self._driver, self.settings, email=self.email, password=self.password,
                cookie_string=self.cookie_string, log=self.on_message)
            self.history.record("auth", success=bool(ok))
            if not ok:
                self.on_message("Authentication failed. Check credentials or log in manually.")
                self.on_finished({"ok": False, "error": "authentication"})
                return

            start = self._first_incomplete(state, dirs)
            self.on_message(f"Starting from scene {start + 1} of {n}")
            self.on_progress(start, n)

            bot = bot_mod.PlaygroundBot(self._driver, self.settings, selectors, log=self.on_message)

            for i in range(start, n):
                if self._stop:
                    break
                scene = state["scenes"][i]
                self.on_stage(f"scene {i + 1}/{n}")
                self.on_progress(i, n)
                self.on_message(f"Scene {i + 1}: {scene['prompt'][:90]}")
                self.history.record("scene_start", scene=i + 1, prompt=scene["prompt"])

                startframe = None
                if i > 0:
                    prev = state["scenes"][i - 1]
                    if self.settings.get("continuation", "i2v") == "v2v":
                        startframe = prev.get("clip")
                    else:
                        startframe = prev.get("link")
                    if not (startframe and Path(startframe).exists()):
                        self.on_message(f"Scene {i + 1} skipped: previous scene output missing.")
                        scene["status"] = STATUS["error"]
                        scene["error"] = "previous scene output missing"
                        self._save_state(state)
                        continue

                scene["status"] = STATUS["generating"]
                scene["attempts"] = scene.get("attempts", 0)
                self._save_state(state)

                srcs = []
                attempts = max(1, int(self.settings.get("retries", 3)))
                is_v2v = self.settings.get("continuation", "i2v") == "v2v"
                for attempt in range(attempts):
                    if self._stop:
                        break
                    try:
                        srcs = bot.generate_and_capture(
                            scene["prompt"], startframe=startframe, v2v=is_v2v)
                    except Exception as exc:
                        self.history.record("scene_error", scene=i + 1, attempt=attempt + 1, error=str(exc)[:200])
                        scene["attempts"] += 1
                        scene["error"] = str(exc)[:200]
                        self._save_state(state)
                        self.on_message(f"Scene {i + 1} attempt {attempt + 1} failed: {exc}")
                        time.sleep(10 * (attempt + 1))
                        continue
                    if srcs:
                        break
                    scene["attempts"] += 1
                    self._save_state(state)
                    self.on_message(f"Scene {i + 1} attempt {attempt + 1}: no output yet.")
                    time.sleep(10 * (attempt + 1))

                if self._stop:
                    break
                if not srcs:
                    scene["status"] = STATUS["error"]
                    scene["error"] = "no output after retries"
                    self._save_state(state)
                    self.history.record("scene_no_output", scene=i + 1)
                    self.on_message(f"Scene {i + 1} failed.")
                    continue

                clip_path = dirs["clips"] / f"scene_{i + 1:03d}.mp4"
                self.on_stage(f"scene {i + 1}/{n} - downloading")
                cookies = {c["name"]: c["value"] for c in self._driver.get_cookies()}
                try:
                    downloader.download_video(srcs[0], clip_path, cookies=cookies, driver=self._driver)
                except Exception as exc:
                    scene["status"] = STATUS["error"]
                    scene["error"] = f"download: {exc}"
                    self._save_state(state)
                    self.on_message(f"Scene {i + 1} download failed: {exc}")
                    continue
                scene["clip"] = str(clip_path)
                scene["status"] = STATUS["downloaded"]
                self._save_state(state)
                self.history.record("scene_downloaded", scene=i + 1, url=srcs[0], clip=str(clip_path))

                link_path = dirs["frames"] / f"scene_{i + 1:03d}_link.png"
                try:
                    frame_extract.extract_last_frame(clip_path, link_path)
                except Exception as exc:
                    scene["error"] = f"extract: {exc}"
                    self._save_state(state)
                    self.on_message(f"Scene {i + 1} frame extraction failed: {exc}")
                    continue
                scene["link"] = str(link_path)
                scene["status"] = STATUS["done"]
                scene["error"] = None
                self._save_state(state)
                self.history.record("scene_done", scene=i + 1, link=str(link_path))
                self.on_progress(i + 1, n)
                self.on_message(f"Scene {i + 1} done -> {clip_path.name}")

            if self._stop:
                self.on_message("Stopped by user.")
                self.on_finished({"ok": False, "error": "stopped"})
                return

            done = [s for s in state["scenes"] if s["status"] == STATUS["done"]
                    and s.get("clip") and Path(s["clip"]).exists()]
            if not done:
                self.on_message("No completed scenes to assemble.")
                self.on_finished({"ok": False, "error": "no completed scenes"})
                return

            width, height = config.target_dims(self.settings)
            self.on_stage("normalizing")
            normalized = []
            for scene in done:
                dst = dirs["normalized"] / f"scene_{scene['index']:03d}.mp4"
                normalize_mod.normalize_clip(
                    scene["clip"], dst, width, height,
                    int(self.settings.get("fps", 24)),
                    keep_audio=bool(self.settings.get("keep_audio", True)),
                    duration_target=float(self.settings.get("duration_target", 20.0)))
                normalized.append(dst)
                self.on_message(f"Normalized scene {scene['index']}")

            self.on_stage("stitching")
            silent = dirs["clips"].parent / "movie_silent.mp4"
            render_mod.concat_clips(normalized, silent)
            self.on_message(f"Stitched {len(normalized)} clips -> {silent}")

            music_track = None
            if self.settings.get("music_bed"):
                self.on_stage("sound design")
                total = len(normalized) * float(self.settings.get("duration_target", 20.0))
                assets = Path(__file__).resolve().parent.parent / "assets"
                music_track = audio_mod.build_track(assets, total, dirs["audio"] / "music_bed.m4a")
                if music_track:
                    self.on_message(f"Music bed built -> {music_track}")
                else:
                    self.on_message("No audio assets found; skipping music bed.")

            self.on_stage("final render")
            final = dirs["clips"].parent / "movie_final.mp4"
            render_mod.final_render(silent, music_track, final)
            self.on_message(f"Final movie -> {final}")
            self._summary = {"ok": True, "scenes_done": len(done), "total": n,
                             "final": str(final)}
            self.history.record("pipeline_done", scenes_done=len(done), final=str(final))
            self.on_finished(self._summary)
        finally:
            if self._driver is not None:
                try:
                    self._driver.quit()
                except Exception:
                    pass