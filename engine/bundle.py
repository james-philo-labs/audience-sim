#!/usr/bin/env python3
"""Freeze local structured article data; never accept arbitrary source HTML or fetch URLs."""
import argparse, hashlib, html, json, re, shutil, subprocess
from urllib.parse import urlsplit
from pathlib import Path
from media import within, validate_seal, ffprobe


def save(p, x):
    p.write_text(json.dumps(x, indent=2, ensure_ascii=False) + '\n')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def inline(text, annotations=None):
    if annotations is None:
        return html.escape(text)
    if not isinstance(annotations, list) or ''.join(x.get('text', '') for x in annotations) != text:
        raise ValueError('Inline annotations must reconstruct exact text')
    parts = []
    for item in annotations:
        kind = item.get('type')
        if kind not in {'text', 'strong', 'em', 'link'} or set(item) != ({'type', 'text', 'href'} if kind == 'link' else {'type', 'text'}):
            raise ValueError('Unsupported inline annotation')
        value = html.escape(item['text'])
        if kind == 'link':
            url = urlsplit(item['href'])
            if url.scheme != 'https' or not url.netloc or url.username or url.password:
                raise ValueError('Only explicit HTTPS source links are supported')
            parts.append('<a href="' + html.escape(item['href'], quote=True) + '">' + value + '</a>')
        elif kind == 'text':
            parts.append(value)
        else:
            parts.append(f'<{kind}>{value}</{kind}>')
    return ''.join(parts)


def freeze(article, out):
    article, out = Path(article).resolve(), Path(out).resolve()
    if out.exists():
        raise ValueError('Use a fresh bundle directory')
    data = json.loads(article.read_text())
    blocks, all_blocks = data['blocks'], []
    for b in blocks:
        all_blocks.append(b)
        if b['type'] == 'callout':
            if not b.get('blocks') or any(x['type'] not in {'paragraph', 'image', 'video', 'image_group'} for x in b['blocks']):
                raise ValueError('Callout accepts paragraph and local media blocks only')
            all_blocks.extend(b['blocks'])
    if not 1 <= len(all_blocks) <= 200:
        raise ValueError('Article must have 1–200 blocks')
    ids = [b['id'] for b in all_blocks]
    if len(set(ids)) != len(ids) or any(not re.fullmatch(r'[a-z0-9-]+', i) for i in ids):
        raise ValueError('Unique simple block IDs required')
    if data['main_end_id'] not in [b['id'] for b in blocks] or next(b for b in blocks if b['id'] == data['main_end_id'])['type'] != 'paragraph':
        raise ValueError('Explicit top-level closing paragraph required')
    if data.get('cover_block_id') and not (blocks[0]['id'] == data['cover_block_id'] and blocks[0]['type'] == 'image'):
        raise ValueError('Cover must be the first image block')
    out.mkdir(parents=True)
    (out / 'source').mkdir()
    (out / 'site/assets').mkdir(parents=True)
    shutil.copy2(article, out / 'source/article.json')
    assets, maps, seen, mapped, placements = [], [], {}, set(), []

    def address(bid, text, section, kind):
        if bid in mapped or not re.fullmatch(r'[a-z0-9-]+', bid):
            raise ValueError('Duplicate or invalid derived block ID: ' + bid)
        mapped.add(bid)
        maps.append({'block_id': bid, 'text': text, 'section_id': section, 'kind': kind})

    def media_tag(b, section):
        bid, kind = b['id'], b['type']
        source = within(article.parent, b['asset'])
        if not source.is_file() or source.stat().st_size > 20000000:
            raise ValueError('Missing or oversized local media')
        mime = {'.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp', '.gif': 'image/gif', '.mp4': 'video/mp4'}.get(source.suffix.lower())
        if not mime or (kind == 'animation' and mime != 'image/gif') or (kind == 'video' and mime != 'video/mp4') or (kind == 'image' and not mime.startswith('image/')):
            raise ValueError('Unsupported media kind')
        aid = 'asset-' + sha(source)[:12]
        target = out / 'site/assets' / (aid + source.suffix.lower())
        shutil.copy2(source, target)
        url = target.relative_to(out / 'site').as_posix()
        if aid not in seen:
            a = {'asset_id': aid, 'reference': b['asset'], 'source_sha256': sha(source), 'frozen_path': target.relative_to(out).as_posix(), 'site_url': url, 'mime_type': mime}
            if mime == 'image/gif':
                poster = target.with_suffix('.png')
                subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', str(source), '-frames:v', '1', str(poster)], check=True)
                a['layout_capture_url'] = poster.relative_to(out / 'site').as_posix()
            if mime in {'video/mp4', 'image/gif'}:
                a['probe'] = ffprobe(source)
            assets.append(a)
            seen[aid] = a
        placement = 'placement-' + bid
        placements.append({'block_id': bid, 'placement_id': placement, 'asset_id': aid, 'section_id': section, 'kind': kind})
        attrs = f'data-block-id="{bid}" data-source-block="{bid}" data-src-asset="{aid}" data-src-placement="{placement}"'
        label = html.escape(b.get('alt', b.get('text', '')), quote=True)
        address(bid, b.get('text', ''), section, kind)
        if kind == 'video':
            address(bid + '-link', 'Inspect clip', section, 'control')
            return f'<video {attrs} src="{url}" aria-label="{label}" muted controls playsinline preload="metadata"></video><a data-ui-control="true" data-block-id="{bid}-link" data-href-placement="link-{bid}" data-href-asset="{aid}" href="{url}">Inspect clip</a>'
        return f'<img {attrs} src="{url}" alt="{label}">'

    def caption(b, section):
        if not b.get('text'):
            return ''
        bid = b['id'] + '-caption'
        address(bid, b['text'], section, 'caption')
        return f'<figcaption data-block-id="{bid}">{inline(b["text"], b.get("inlines"))}</figcaption>'

    def render(b, inherited='unallocated'):
        bid, kind, section = b['id'], b['type'], b.get('section_id', inherited)
        if not re.fullmatch(r'[a-z0-9-]+', section):
            raise ValueError('Invalid section ID')
        attrs = f'data-block-id="{bid}" data-source-block="{bid}"'
        text = b.get('text', '')
        if kind in {'paragraph', 'heading'}:
            address(bid, text, section, kind)
            tag = 'p' if kind == 'paragraph' else 'h2'
            return f'<{tag} {attrs}>{inline(text, b.get("inlines"))}</{tag}>'
        if kind == 'details':
            address(bid, text, section, kind)
            address(bid + '-summary', b['summary'], section, 'summary')
            address(bid + '-body', text, section, 'paragraph')
            return f'<details {attrs}><summary data-block-id="{bid}-summary">{html.escape(b["summary"])}</summary><p data-block-id="{bid}-body">{html.escape(text)}</p></details>'
        if kind in {'image', 'animation', 'video'}:
            return '<figure>' + media_tag(b, section) + caption(b, section) + '</figure>'
        if kind == 'image_group':
            if not 2 <= len(b['images']) <= 4:
                raise ValueError('Image group needs two to four images')
            tags = [media_tag({**x, 'type': 'image'}, section) for x in b['images']]
            address(bid, text, section, kind)
            return f'<figure {attrs} class="image-pair"><div class="image-row">' + ''.join(tags) + '</div>' + caption(b, section) + '</figure>'
        if kind == 'table':
            headers, rows = b['headers'], b['rows']
            if not 1 <= len(headers) <= 6 or not 1 <= len(rows) <= 30 or any(len(row) != len(headers) for row in rows):
                raise ValueError('Invalid table dimensions')
            address(bid, '', section, kind)
            rendered = []
            for ri, row in enumerate([headers] + rows):
                cells = []
                for ci, value in enumerate(row):
                    cell = f'{bid}-r{ri}-c{ci}'
                    if not isinstance(value, str):
                        raise ValueError('Table cells must be strings')
                    address(cell, value, section, 'table_cell')
                    tag = 'th' if ri == 0 else 'td'
                    cells.append(f'<{tag} data-block-id="{cell}">{html.escape(value)}</{tag}>')
                rendered.append('<tr>' + ''.join(cells) + '</tr>')
            return f'<table {attrs}><thead>' + rendered[0] + '</thead><tbody>' + ''.join(rendered[1:]) + '</tbody></table>'
        if kind == 'callout':
            address(bid, '', section, kind)
            address(bid + '-label', b['label'], section, 'label')
            return f'<aside {attrs} class="external-comparison"><p data-block-id="{bid}-label">{html.escape(b["label"])}</p>' + ''.join(render(x, section) for x in b['blocks']) + '</aside>'
        raise ValueError('Unsupported block type ' + kind)

    title = html.escape(data['title'])
    address('title', data['title'], 'opening', 'heading')
    title_html = '<h1 data-block-id="title">' + title + '</h1>'
    pieces = []
    if not data.get('cover_block_id'):
        pieces.append(title_html)
    for i, b in enumerate(blocks):
        pieces.append(render(b))
        if i == 0 and data.get('cover_block_id'):
            pieces.append(title_html)
        if b['id'] == data['main_end_id']:
            pieces.append('<!-- MAIN_BODY_END -->')
    css = 'body{margin:0;background:#f7f8f2;color:#1b3025;font:19px/1.65 system-ui,sans-serif}*{box-sizing:border-box}article{max-width:880px;margin:48px auto;padding:0 32px 100px}h1{font-size:44px;line-height:1.15}h2{margin-top:48px}p{margin:28px 0}figure{margin:40px 0}img,video{display:block;max-width:100%;max-height:460px;width:auto;height:auto;margin:auto}figcaption{font-size:16px;margin-top:12px}details{margin:40px 0;border:1px solid #a4b39b;padding:20px}button{padding:12px;font:inherit}.image-row{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:center}.image-row img{max-width:100%}table{width:100%;border-collapse:collapse;font-size:17px}th,td{text-align:left;vertical-align:top;border:1px solid #bcc9b3;padding:12px;overflow-wrap:anywhere}aside.external-comparison{border-left:4px solid #a4b39b;padding:0 20px;margin:32px 0}aside figure{margin:20px 0}@media(max-width:600px){article{padding:0 20px 70px}h1{font-size:34px}.image-row{grid-template-columns:1fr}}'
    (out / 'site/article.css').write_text(css)
    (out / 'site/index.html').write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'self\'; img-src \'self\'; media-src \'self\'; base-uri \'none\'; form-action \'none\'"><link rel="stylesheet" href="article.css"><title>' + title + '</title></head><body><article>' + ''.join(pieces) + '</article></body></html>')
    save(out / 'block-map.json', maps)
    native = []
    for c in data.get('native_cases', []):
        match = next(a for a in assets if a['reference'] == c['asset'])
        native.append({'case_id': c['case_id'], 'asset_id': match['asset_id'], 'audio_enabled': c['audio_enabled']})
    save(out / 'bundle-manifest.json', {'version': 'public-bundle-0.2', 'article_id': data['id'], 'article_version': data['version'], 'article_sha256': sha(article), 'upstream_source_sha256': data.get('source_markdown_sha256'), 'assets': assets, 'placements': placements, 'sections': data.get('sections', []), 'native_cases': native, 'media_policy': 'Local source bytes only. No model inference. GIF capture posters are frozen first frames; playback stays separate.'})
    save(out / 'seal.json', {'files': {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*')) if p.is_file()}})
    validate_seal(out)
    return {'status': 'frozen_not_observed', 'bundle': str(out), 'assets': len(assets), 'model_calls': 0}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--article', required=True)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    print(json.dumps(freeze(a.article, a.out)))
