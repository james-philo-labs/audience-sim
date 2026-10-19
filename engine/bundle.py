#!/usr/bin/env python3
"""Freeze an explicit local article specification. No fetching and no model calls."""

import argparse, html, json, hashlib, shutil, re, subprocess
from pathlib import Path
from media import within, validate_seal, ffprobe


def save(p, x):
    p.write_text(json.dumps(x, indent=2, ensure_ascii=False) + "\n")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def freeze(article, out):
    article = Path(article).resolve()
    out = Path(out).resolve()
    if out.exists():
        raise ValueError("Use a fresh bundle directory")
    data = json.loads(article.read_text())
    blocks = data["blocks"]
    if not 1 <= len(blocks) <= 200:
        raise ValueError("Article must have 1–200 blocks")
    ids = [b["id"] for b in blocks]
    if len(set(ids)) != len(ids) or any(
        not re.fullmatch(r"[a-z0-9-]+", i) for i in ids
    ):
        raise ValueError("Unique simple block IDs required")
    if (
        data["main_end_id"] not in ids
        or next(b for b in blocks if b["id"] == data["main_end_id"])["type"]
        != "paragraph"
    ):
        raise ValueError("Explicit closing paragraph required")
    out.mkdir(parents=True)
    (out / "source").mkdir()
    (out / "site/assets").mkdir(parents=True)
    shutil.copy2(article, out / "source/article.json")
    assets = []
    maps = []
    pieces = []
    seen = {}
    for b in blocks:
        kind = b["type"]
        bid = b["id"]
        attrs = f'data-block-id="{bid}" data-source-block="{bid}"'
        text = b.get("text", "")
        esc = html.escape(text)
        if kind in ["paragraph", "heading"]:
            tag = "p" if kind == "paragraph" else "h2"
            fragment = f"<{tag} {attrs}>{esc}</{tag}>"
        elif kind == "details":
            summary = html.escape(b["summary"])
            fragment = f'<details {attrs}><summary data-block-id="{bid}-summary">{summary}</summary><p data-block-id="{bid}-body">{esc}</p></details>'
            maps += [
                {"block_id": bid + "-summary", "text": b["summary"]},
                {"block_id": bid + "-body", "text": text},
            ]
        elif kind in ["image", "animation", "video"]:
            source = within(article.parent, b["asset"])
            if not source.is_file() or source.stat().st_size > 20000000:
                raise ValueError("Missing or oversized local media")
            mime = {
                ".svg": "image/svg+xml",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".webp": "image/webp",
                ".gif": "image/gif",
                ".mp4": "video/mp4",
            }.get(source.suffix.lower())
            if (
                not mime
                or (kind == "animation" and mime != "image/gif")
                or (kind == "video" and mime != "video/mp4")
                or (kind == "image" and not mime.startswith("image/"))
            ):
                raise ValueError("Unsupported media kind")
            aid = "asset-" + sha(source)[:12]
            target = out / "site/assets" / (aid + source.suffix.lower())
            shutil.copy2(source, target)
            url = str(target.relative_to(out / "site"))
            if aid not in seen:
                a = {
                    "asset_id": aid,
                    "reference": b["asset"],
                    "source_sha256": sha(source),
                    "frozen_path": str(target.relative_to(out)),
                    "site_url": url,
                    "mime_type": mime,
                }
                if mime == "image/gif":
                    poster = target.with_suffix(".png")
                    subprocess.run(
                        [
                            "ffmpeg",
                            "-nostdin",
                            "-y",
                            "-v",
                            "error",
                            "-i",
                            str(source),
                            "-frames:v",
                            "1",
                            str(poster),
                        ],
                        check=True,
                    )
                    a["layout_capture_url"] = str(poster.relative_to(out / "site"))
                if mime == "video/mp4" or mime == "image/gif":
                    a["probe"] = ffprobe(source)
                assets.append(a)
                seen[aid] = a
            label = html.escape(b.get("alt", text), quote=True)
            placement = "placement-" + bid
            if kind == "video":
                fragment = f'<figure><video {attrs} data-src-asset="{aid}" data-src-placement="{placement}" src="{url}" muted controls preload="metadata"></video><a data-block-id="{bid}-link" data-href-placement="link-{bid}" data-href-asset="{aid}" href="{url}">Inspect clip</a><figcaption data-block-id="{bid}-caption">{esc}</figcaption></figure>'
                maps.append({"block_id": bid + "-link", "text": "Inspect clip"})
            else:
                fragment = f'<figure><img {attrs} data-src-asset="{aid}" data-src-placement="{placement}" src="{url}" alt="{label}"><figcaption data-block-id="{bid}-caption">{esc}</figcaption></figure>'
            maps.append({"block_id": bid + "-caption", "text": text})
        else:
            raise ValueError("Unsupported block type " + kind)
        maps.append({"block_id": bid, "text": text})
        pieces.append(fragment)
        if bid == data["main_end_id"]:
            pieces.append("<!-- MAIN_BODY_END -->")
    css = "body{margin:0;background:#f7f8f2;color:#1b3025;font:19px/1.65 system-ui,sans-serif}article{max-width:880px;margin:48px auto;padding:0 32px 100px}h1{font-size:44px;line-height:1.15}h2{margin-top:48px}p{margin:28px 0}figure{margin:40px 0}img,video{display:block;max-width:100%;max-height:460px;margin:auto}figcaption{font-size:16px}details{margin:40px 0;border:1px solid #a4b39b;padding:20px}button{padding:12px;font:inherit}"
    (out / "site/article.css").write_text(css)
    title = html.escape(data["title"])
    page = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'self\'; img-src \'self\'; media-src \'self\'; base-uri \'none\'; form-action \'none\'"><link rel="stylesheet" href="article.css"><title>'
        + title
        + '</title></head><body><article><h1 data-block-id="title">'
        + title
        + "</h1>"
        + "".join(pieces)
        + "</article></body></html>"
    )
    maps.insert(0, {"block_id": "title", "text": data["title"]})
    (out / "site/index.html").write_text(page)
    save(out / "block-map.json", maps)
    native = []
    for c in data.get("native_cases", []):
        match = next(a for a in assets if a["reference"] == c["asset"])
        native.append(
            {
                "case_id": c["case_id"],
                "asset_id": match["asset_id"],
                "audio_enabled": c["audio_enabled"],
            }
        )
    save(
        out / "bundle-manifest.json",
        {
            "version": "public-bundle-0.1",
            "article_id": data["id"],
            "article_version": data["version"],
            "article_sha256": sha(article),
            "assets": assets,
            "native_cases": native,
            "media_policy": "Local source bytes only. No model inference. GIF capture posters are frozen first frames; playback stays separate.",
        },
    )
    save(
        out / "seal.json",
        {
            "files": {
                str(p.relative_to(out)): sha(p)
                for p in sorted(out.rglob("*"))
                if p.is_file()
            }
        },
    )
    validate_seal(out)
    return {
        "status": "frozen_not_observed",
        "bundle": str(out),
        "assets": len(assets),
        "model_calls": 0,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--article", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    print(json.dumps(freeze(a.article, a.out)))
