"""Frozen-file and media helpers. No model requests."""

from pathlib import Path
import hashlib, json, subprocess


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def cmd(args):
    p = subprocess.run(args, text=True, capture_output=True, timeout=180)
    if p.returncode:
        raise ValueError(f"{args[0]} failed; exit {p.returncode}")
    return p.stdout


def ffprobe(path, frames=False):
    args = ["ffprobe", "-v", "error"]
    if frames:
        args += ["-select_streams", "v:0", "-show_frames"]
    args += [
        "-show_entries",
        "frame=best_effort_timestamp_time"
        if frames
        else "format=duration:stream=codec_type,codec_name,nb_frames,width,height",
        "-of",
        "json",
        str(path),
    ]
    return json.loads(cmd(args))


def validate_seal(bundle):
    seal = read(bundle / "seal.json")
    files = seal["files"]
    actual = {
        str(p.relative_to(bundle))
        for p in bundle.rglob("*")
        if p.is_file() and p.name != "seal.json"
    }
    if actual != set(files):
        raise ValueError("Frozen bundle file set changed")
    for rel, digest in files.items():
        path = within(bundle, rel)
        if sha(path) != digest:
            raise ValueError("Frozen bundle hash mismatch: " + rel)
    return sha(bundle / "seal.json")


def within(root, relative):
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        raise ValueError("Path outside run/bundle")
    return path
