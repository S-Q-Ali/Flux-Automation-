import subprocess
from pathlib import Path

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"}


def find_assets(assets_root):
    groups = {}
    for name in ("music", "ambience", "foley"):
        folder = Path(assets_root) / name
        files = []
        if folder.exists():
            files = [p for p in folder.iterdir() if p.suffix.lower() in AUDIO_EXTS]
        groups[name] = files
    return groups


def build_track(assets_root, duration, out_path):
    groups = find_assets(assets_root)
    inputs = []
    volumes = []
    index = 0
    for name, volume in (("ambience", 0.4), ("foley", 0.5), ("music", 0.28)):
        for p in groups[name]:
            inputs.append(["-stream_loop", "-1", "-t", f"{duration}", "-i", str(p)])
            volumes.append((index, f"volume={volume}"))
            index += 1
    if not inputs:
        return None

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for inp in inputs:
        cmd += inp
    labels = [f"[v{i}]" for i in range(index)]
    parts = []
    for i, v in volumes:
        parts.append(f"[{i}:a]{v}[v{i}]")
    mix_inputs = "".join(labels)
    parts.append(f"{mix_inputs}amix=inputs={index}:normalize=0,"
                 f"afade=t=in:st=0:d=3,afade=t=out:st={max(0, duration - 3)}:d=3[out]")
    cmd += ["-filter_complex", ";".join(parts)]
    cmd += ["-map", "[out]", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(out_path)]
    subprocess.run(cmd, check=True)
    return out_path