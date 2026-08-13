import json
from pathlib import Path

DEFAULT_SELECTORS = {
    "prompt_input": [
        "textarea[placeholder='Describe what you want to generate...']",
        "textarea",
        "div[contenteditable='true']",
        "*[role='textbox']",
        "*[data-placeholder]",
    ],
    "generate_button": [
        "button[aria-label='Generate']",
        "button",
        "*[role='button']",
    ],
    "generate_texts": ["Generate", "Create", "Submit", "Run", "Animate", "Make video"],
    "start_frame_upload": [
        "input[type='file'][accept='image/*']",
        "input[type='file']",
    ],
    "start_video_upload": [
        "input[type='file'][accept='video/mp4']",
        "input[type='file'][type='file']",
    ],
    "video_elements": ["video"],
    "ready_texts": ["Ready", "Download", "Downloaded", "Complete", "Finished", "Done"],
    "generating_texts": ["Generating", "In queue", "Queued", "Processing", "Pending"],
}


def load_selectors(settings):
    selectors = {k: list(v) for k, v in DEFAULT_SELECTORS.items()}
    path = Path(__file__).resolve().parent.parent / "recon" / "selectors.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for k, v in data.items():
                if isinstance(v, list) and v:
                    selectors[k] = v
        except Exception:
            pass
    return selectors


def save_selectors(selectors):
    path = Path(__file__).resolve().parent.parent / "recon" / "selectors.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(selectors, indent=2, ensure_ascii=False), encoding="utf-8")