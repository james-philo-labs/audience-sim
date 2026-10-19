"""Verify the deliberately small public file set. Never scans generated run archives."""

from pathlib import Path
import hashlib, json, re, subprocess

ROOT = Path(__file__).resolve().parents[1]
SKIP = {
    "node_modules",
    ".ruff_cache",
    ".git",
    "runs",
    "artifacts",
    "__pycache__",
    "test-results",
    "playwright-report",
}
MAX_FILE = 1000000


def files():
    return sorted(
        p
        for p in ROOT.rglob("*")
        if p.is_file()
        and not SKIP.intersection(p.relative_to(ROOT).parts)
        and not p.name.endswith((".log", ".pyc"))
        and p.name != ".DS_Store"
    )


def main(check_inventory=True):
    paths = files()
    errors = []
    manifest_path = ROOT / "PUBLIC_ASSETS.json"
    listed = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    # Patterns are built as pieces so the checker does not flag its own source.
    forbidden = [
        "/" + "Users/",
        "Philo" + "-GTM",
        "Simulation" + "-Agent",
        "notes." + "granola.ai",
        "philolabs." + "slack.com",
        "company" + "verse",
        "Chris" + "tine",
        "james@" + "philolabs.ai",
        "team_" + "hsKEN",
        "prj_" + "CRiI",
        "dpl_" + "AmiU",
    ]
    secrets = [
        r"sk-[A-Za-z0-9_-]{24,}",
        r"gh[pousr]_[A-Za-z0-9]{24,}",
        r"AIza[A-Za-z0-9_-]{30,}",
        r"BEGIN [A-Z ]*PRIVATE KEY",
    ]
    for p in paths:
        rel = str(p.relative_to(ROOT))
        if p.stat().st_size > MAX_FILE:
            errors.append(rel + ": exceeds 1 MB file limit")
        if p.suffix.lower() in {".mp4", ".gif", ".png", ".jpg", ".webp"}:
            continue
        try:
            text = p.read_text(errors="strict")
        except UnicodeDecodeError:
            errors.append(rel + ": unexpected binary file")
            continue
        for pattern in forbidden:
            if pattern in text:
                errors.append(rel + ": disallowed internal identifier/path")
        if any(re.search(x, text) for x in secrets):
            errors.append(rel + ": possible credential")
        if p.suffix == ".md":
            for link in re.findall(r"\]\(([^)]+)\)", text):
                if link.startswith(("https://", "http://", "mailto:", "#")):
                    continue
                target = link.split("#")[0]
                if target and not (p.parent / target).is_file():
                    errors.append(rel + ": broken relative link " + link)
    if check_inventory and listed is not None:
        actual = {
            str(p.relative_to(ROOT)) for p in paths if p.name != "PUBLIC_ASSETS.json"
        }
        if actual != set(listed["files"]):
            errors.append("Public allowlist differs from file set")
        for rel, h in listed["files"].items():
            p = ROOT / rel
            if p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest() != h:
                errors.append(
                    rel
                    + ": public inventory hash changed; review and reseal intentionally"
                )
    if (ROOT / ".git").exists():
        tracked = (
            subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
            .decode()
            .split("\0")
        )
        if any(SKIP.intersection(Path(x).parts) for x in tracked if x):
            errors.append("Generated/runtime directory tracked by git")
    result = {
        "status": "failed" if errors else "passed",
        "public_files": len(paths),
        "bytes": sum(p.stat().st_size for p in paths),
        "errors": errors,
        "scope": "Static checks and explicit inventory; not a guarantee against every possible secret.",
    }
    print(json.dumps(result, indent=2))
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
