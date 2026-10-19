"""Create tiny, original diagnostic media. FFmpeg only; no model calls or downloads."""

from pathlib import Path
import subprocess

P = Path(__file__).resolve().parents[1] / "examples/assets"
P.mkdir(exist_ok=True)
(P / "diagram.svg").write_text(
    """<svg xmlns="http://www.w3.org/2000/svg" width="800" height="240" viewBox="0 0 800 240"><rect width="800" height="240" fill="#eaf0e0"/><g fill="#244333" font-family="sans-serif" font-size="23"><text x="30" y="72">Trigger → Observe → Reproduce</text><text x="30" y="130">Proposed check ≠ completed repair</text><text x="30" y="190">Authored software fixture</text></g></svg>"""
)


def run(*a):
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", *a], check=True)


run(
    "-f",
    "lavfi",
    "-i",
    "testsrc2=size=192x108:rate=5:duration=2",
    "-loop",
    "0",
    str(P / "motion.gif"),
)
run(
    "-f",
    "lavfi",
    "-i",
    "testsrc2=size=320x180:rate=10:duration=4",
    "-f",
    "lavfi",
    "-i",
    "sine=frequency=880:sample_rate=48000:duration=4",
    "-c:v",
    "libx264",
    "-pix_fmt",
    "yuv420p",
    "-crf",
    "28",
    "-c:a",
    "aac",
    "-shortest",
    "-movflags",
    "+faststart",
    str(P / "tone.mp4"),
)
print("Created original example media; no real audience or model observations.")
