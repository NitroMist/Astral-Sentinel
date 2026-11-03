"""Private, on-disk observation journal and optional local Joplin bridge.

No cloud services, authentication token storage, or third-party dependencies.
AGPL-3.0-or-later.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from urllib.parse import urlencode
from urllib.request import build_opener, ProxyHandler, Request
from urllib.error import URLError, HTTPError
import json
import os
import re
import tempfile
import uuid

DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
LOCK = RLock()
JOPLIN_PORTS = range(41184, 41195)
OPENER = build_opener(ProxyHandler({}))  # Never send loopback traffic through a proxy.


def _db_path(root: Path) -> Path:
    return root / 'data' / 'observations.json'


def read_log(root: Path) -> list[dict]:
    path = _db_path(root)
    if not path.exists():
        return []
    with path.open('r', encoding='utf-8') as handle:
        obj = json.load(handle)
    if not isinstance(obj, dict) or not isinstance(obj.get('entries'), list):
        raise ValueError('Observation database has an invalid format.')
    return obj['entries']


def _write_log(root: Path, entries: list[dict]):
    path = _db_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps({'version': 1, 'entries': entries}, ensure_ascii=False, indent=2).encode('utf-8')
    fd, tmp = tempfile.mkstemp(prefix='.observations-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def create_entry(root: Path, payload: dict, snapshot_fn) -> dict:
    day = str(payload.get('date', ''))
    if not DATE_RE.fullmatch(day):
        raise ValueError('Choose a valid observation date.')
    try:
        datetime.strptime(day, '%Y-%m-%d')
    except ValueError as exc:
        raise ValueError('Choose a valid calendar date.') from exc
    rating = payload.get('observed_difficulty')
    if isinstance(rating, bool) or not isinstance(rating, (int, float)) or not 1 <= rating <= 10:
        raise ValueError('Experienced difficulty must be between 1 and 10.')
    note = payload.get('note', '')
    if not isinstance(note, str) or not note.strip() or len(note) > 12000:
        raise ValueError('Enter an observation (maximum 12,000 characters).')
    chart_time = str(payload.get('chart_at_utc', ''))
    try:
        dt = datetime.fromisoformat(chart_time.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            raise ValueError()
        dt = dt.astimezone(timezone.utc)
        if not 1900 <= dt.year <= 2100:
            raise ValueError()
    except ValueError as exc:
        raise ValueError('Invalid chart reference time.') from exc
    options = payload.get('options') or {}
    if not isinstance(options, dict):
        raise ValueError('Invalid chart options.')
    house = options.get('house', 'placidus')
    zodiac = options.get('zodiac', 'tropical')
    method = options.get('house_method', 'longitude')
    node = options.get('node_mode', 'mean')
    lilith = options.get('lilith_mode', 'mean')
    scoring = options.get('aux_scoring', True)
    if house not in ('placidus','whole','equal') or zodiac not in ('tropical','sidereal_lahiri') or method not in ('longitude','spatial'):
        raise ValueError('Invalid chart reference configuration.')
    if node not in ('mean','true') or lilith not in ('mean','osculating') or not isinstance(scoring, bool):
        raise ValueError('Invalid auxiliary configuration.')
    chart = snapshot_fn(dt, house, zodiac, house_method=method, node_mode=node,
                        lilith_mode=lilith, aux_scoring=scoring)
    score = chart['score']
    record = {
        'id': uuid.uuid4().hex,
        'profile_id': chart['birth_profile'].get('id', 'original'),
        'profile_label': chart['birth_profile'].get('label', 'Birth chart'),
        'date': day,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'observed_difficulty': round(float(rating), 1),
        'note': note.strip(),
        'chart_at_utc': chart['at_utc'],
        'predicted_difficulty': score['difficulty'],
        'planetary_baseline': score.get('planetary_baseline', score['difficulty']),
        'auxiliary_modifier': score.get('auxiliary_modifier', 0),
        'chart_settings': {'house_system': house, 'house_method': method, 'zodiac': zodiac,
                           'node_mode': node, 'lilith_mode': lilith, 'aux_scoring': scoring},
        'leading_aspects': [f"{a['transit']} {a['type']} natal {a['natal']} ({a['orb']:.2f}°)"
                            for a in chart.get('aspects', [])[:5]],
        'joplin_note_id': None,
    }
    with LOCK:
        entries = read_log(root)
        if len(entries) >= 2000:
            raise ValueError('Journal has reached its 2,000-entry limit. Export a backup first.')
        entries.insert(0, record)
        _write_log(root, entries)
    return record


def delete_entry(root: Path, entry_id: str) -> bool:
    with LOCK:
        entries = read_log(root)
        remaining = [e for e in entries if e.get('id') != entry_id]
        if len(remaining) == len(entries):
            return False
        _write_log(root, remaining)
        return True


def one_entry(root: Path, entry_id: str) -> dict:
    with LOCK:
        for e in read_log(root):
            if e.get('id') == entry_id:
                return e
    raise ValueError('Observation not found.')


def markdown_entry(entry: dict) -> str:
    s = entry['chart_settings']
    aspects = '\n'.join(f'- {a}' for a in entry.get('leading_aspects', [])) or '- None'
    return (f"# Astral Sentinel Observation · {entry['date']}\n\n"
            f"**Birth chart:** {entry.get('profile_label', 'Unspecified chart')}  \n"
            f"**Experienced difficulty:** {entry['observed_difficulty']:.1f}/10  \n"
            f"**Astrological index:** {entry['predicted_difficulty']:.1f}/10  \n"
            f"**Planetary baseline:** {entry['planetary_baseline']:.1f}/10  \n"
            f"**Auxiliary adjustment:** {entry['auxiliary_modifier']:+.2f}  \n"
            f"**Chart moment (UTC):** {entry['chart_at_utc']}  \n"
            f"**Chart options:** {s['zodiac']} · {s['house_system']} · {s['house_method']} · "
            f"nodes {s['node_mode']} · Lilith {s['lilith_mode']} · auxiliary scoring {s['aux_scoring']}\n\n"
            f"## What happened / how it felt\n\n{entry['note']}\n\n"
            f"## Top planetary aspects at chart moment\n\n{aspects}\n\n"
            f"---\n*The astrological index is an interpretive experiment, not an objective risk or event prediction. "
            f"Recorded locally by Astral Sentinel.*\n")


def markdown_all(entries: list[dict]) -> str:
    return '# Astral Sentinel · Observation Log\n\n' + ('\n\n---\n\n'.join(markdown_entry(e) for e in entries) if entries else '_No observations saved yet._\n')


def _joplin(port: int, route: str, token: str | None = None, payload: dict | None = None):
    if type(port) is not int or port not in JOPLIN_PORTS:
        raise ValueError('Joplin port must be between 41184 and 41194.')
    if token is not None and (not isinstance(token, str) or not 10 <= len(token) <= 256 or not re.fullmatch(r'[A-Za-z0-9]+', token)):
        raise ValueError('Invalid Joplin API token.')
    url = f'http://127.0.0.1:{port}{route}'
    if token:
        url += ('&' if '?' in url else '?') + urlencode({'token': token})
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8') if payload is not None else None
    req = Request(url, data=data, headers={'Content-Type': 'application/json', 'Accept': 'application/json'} if data is not None else {}, method='POST' if data is not None else 'GET')
    try:
        with OPENER.open(req, timeout=3) as res:
            body = res.read(1024 * 1024)
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise ValueError('Joplin rejected the API token. Check Web Clipper settings.') from None
        raise ValueError(f'Joplin returned HTTP {exc.code}.') from None
    except (URLError, TimeoutError, OSError) as exc:
        raise ValueError('Cannot connect to Joplin. Start the desktop app and enable Web Clipper.') from exc
    if route == '/ping':
        return body.decode('utf-8', 'replace').strip()
    try:
        return json.loads(body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError('Unexpected response from Joplin.') from exc


def find_joplin_port():
    for port in JOPLIN_PORTS:
        try:
            if _joplin(port, '/ping') == 'JoplinClipperServer':
                return port
        except ValueError:
            continue
    return None


def send_to_joplin(root: Path, entry_id: str, token: str, port: int):
    with LOCK:
        entry = one_entry(root, entry_id)
        if entry.get('joplin_note_id'):
            raise ValueError('Already sent to Joplin. No duplicate created.')
        if _joplin(port, '/ping') != 'JoplinClipperServer':
            raise ValueError('The selected port is not a Joplin Web Clipper service.')
        # Dedicated notebook; never touch existing notes or notebooks.
        notebook_id = None
        for page in range(1, 51):
            result = _joplin(port, f'/folders?fields=id,title&limit=100&page={page}', token)
            for f in result.get('items', []):
                if f.get('title') == 'Astral Sentinel Observations':
                    notebook_id = f['id']
                    break
            if notebook_id or not result.get('has_more'):
                break
        if not notebook_id:
            folder = _joplin(port, '/folders', token, {'title': 'Astral Sentinel Observations'})
            notebook_id = folder['id']
        note = _joplin(port, '/notes', token, {
            'parent_id': notebook_id,
            'title': f"Astral Sentinel · {entry['date']} · Observation",
            'body': markdown_entry(entry),
        })
        if not isinstance(note, dict) or not note.get('id'):
            raise ValueError('Joplin did not return a note ID; check Joplin for the note before retrying.')
        entries = read_log(root)
        for record in entries:
            if record.get('id') == entry_id:
                record['joplin_note_id'] = note['id']
                record['joplin_sent_at'] = datetime.now(timezone.utc).isoformat()
        _write_log(root, entries)
        return {'note_id': note['id'], 'notebook': 'Astral Sentinel Observations'}
