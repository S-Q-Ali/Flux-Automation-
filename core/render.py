import subprocess
from pathlib import Path


def concat_clips(clip_paths, out_path, reencode=False):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    list_file = out_path.with_suffix(".txt")
    list_file.write_text(
        "".join(f"file '{str(Path(p).resolve()).replace(chr(39), chr(39) + chr(92) + chr(39))}'\n" for p in clip_paths),
        encoding="utf-8",
    )
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(list_file)]
    if reencode:
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-c", "copy"]
    cmd += ["-movflags", "+faststart", str(out_path)]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        if not reencode:
            return concat_clips(clip_paths, out_path, reencode=True)
        raise
    return out_path


def final_render(video_path, audio_path, out_path):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if audio_path is None:
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
               "-i", str(video_path), "-c", "copy", "-movflags", "+faststart", str(out_path)]
    else:
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
               "-i", str(video_path), "-i", str(audio_path),
               "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
               "-movflags", "+faststart", str(out_path)]
    subprocess.run(cmd, check=True)
    return out_path