"""Local birth-profile library. No cloud lookup, external authentication or PDF parsing.

Copyright (c) 2026 Astral Sentinel contributors; AGPL-3.0-or-later.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import json
import math
import os
import re
import tempfile
import threading
import uuid

LOCK = threading.RLock()
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
TIME_RE = re.compile(r'^\d{2}:\d{2}$')
ID_RE = re.compile(r'^[a-z0-9][a-z0-9_-]{0,63}$')
MAX_PROFILES = 60


def _path(root):
    return Path(root) / 'data' / 'profiles.json'


def _default_entry(root):
    source = Path(root) / 'data' / 'profile.json'
    if source.is_file():
        old = json.loads(source.read_text(encoding='utf-8'))
    else:
        # Defer to existing built-in default only when the legacy file is absent.
        from engine import DEFAULT_PROFILE
        old = DEFAULT_PROFILE
    obj = dict(old)
    obj['id'] = 'original'
    obj['reference_pdf'] = (Path(root) / 'data' / 'reference_chart.json').is_file()  # Local, private optional reference.
    return obj


def read_library(root):
    path = _path(root)
    if not path.exists():
        item = _default_entry(root)
        return {'version': 1, 'active_id': 'original', 'profiles': [item]}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get('profiles'), list) or not data['profiles']:
        raise ValueError('Birth profile library is invalid. Restore data/profiles.json from backup.')
    if data.get('active_id') not in [p.get('id') for p in data['profiles'] if isinstance(p, dict)]:
        raise ValueError('Birth profile library has an invalid active profile.')
    return data


def _atomic_write(root, obj):
    path = _path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(obj, ensure_ascii=False, indent=2).encode('utf-8')
    fd, tmp = tempfile.mkstemp(prefix='.astral-profiles-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def birth_utc(birth, *, require_explicit_fold=False):
    if not isinstance(birth, dict):
        raise ValueError('Birth details must be a JSON object.')
    date = birth.get('date', '')
    time = birth.get('time', '')
    if not isinstance(date, str) or not DATE_RE.fullmatch(date):
        raise ValueError('Enter a complete birth date (YYYY-MM-DD).')
    if not isinstance(time, str) or not TIME_RE.fullmatch(time):
        raise ValueError('Enter the birth clock time (HH:MM, 24-hour format).')
    try:
        naive = datetime.fromisoformat(date + 'T' + time)
    except ValueError as exc:
        raise ValueError('Birth date or time is not a valid calendar value.') from exc
    if not 1900 <= naive.year <= 2100:
        raise ValueError('Birth years from 1900 through 2100 are supported.')
    zone = birth.get('timezone', '')
    if not isinstance(zone, str) or not zone or len(zone) > 100:
        raise ValueError('Enter a valid IANA time zone, e.g. America/Los_Angeles.')
    try:
        tz = ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError, KeyError) as exc:
        raise ValueError('Unknown IANA time zone. Choose a city or use a valid zone name.') from exc
    # Detect a non-existent spring-forward hour or ambiguous fall-back hour.
    options = []
    for fold in (0, 1):
        aware = naive.replace(tzinfo=tz, fold=fold)
        utc = aware.astimezone(timezone.utc)
        if utc.astimezone(tz).replace(tzinfo=None) == naive:
            options.append((fold, utc))
    if not options:
        raise ValueError('This local clock time did not exist due to a daylight-saving change. Verify the time.')
    ambiguous = len(options) == 2 and options[0][1] != options[1][1]
    raw_fold = birth.get('fold', None)
    if ambiguous and raw_fold is None and require_explicit_fold:
        raise ValueError('This birth time occurred twice when clocks changed. Select first or second occurrence.')
    if raw_fold is not None and (type(raw_fold) is not int or raw_fold not in (0, 1)):
        raise ValueError('Clock occurrence must be automatic, first (0), or second (1).')
    chosen = next((dt for f, dt in options if f == (raw_fold if raw_fold is not None else 0)), None)
    if chosen is None:
        raise ValueError('The selected clock occurrence is not valid for this birth date.')
    return chosen


def validate_profile(obj, *, require_explicit_fold=True):
    if not isinstance(obj, dict):
        raise ValueError('Profile must be a JSON object.')
    label = obj.get('label', '')
    if not isinstance(label, str) or not 1 <= len(label.strip()) <= 70:
        raise ValueError('Give this chart a name (1–70 characters).')
    birth = obj.get('birth')
    if not isinstance(birth, dict):
        raise ValueError('Provide the birth information.')
    result_birth = {key: birth.get(key) for key in ('date','time','timezone')}
    for name, minimum, maximum in (('latitude',-90,90), ('longitude',-180,180)):
        try:
            value = birth[name]
            if isinstance(value, bool):
                raise ValueError()
            value = float(value)
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError('Enter a numerical '+name+' in decimal degrees.') from exc
        if not math.isfinite(value) or not minimum <= value <= maximum:
            raise ValueError(name.title()+' must be between '+str(minimum)+' and '+str(maximum)+'.')
        result_birth[name] = round(value, 7)
    place = birth.get('location_label', '')
    if not isinstance(place, str) or len(place) > 120:
        raise ValueError('Birthplace label must be no longer than 120 characters.')
    result_birth['location_label'] = place.strip() or 'Custom coordinates'
    fold = birth.get('fold')
    if fold not in (None, 0, 1) or isinstance(fold, bool):
        raise ValueError('Invalid daylight-saving clock occurrence.')
    if fold is not None:
        result_birth['fold'] = fold
    resolved = birth_utc(result_birth, require_explicit_fold=require_explicit_fold)
    hs = obj.get('default_house_system', 'placidus')
    zodiac = obj.get('default_zodiac','tropical')
    if hs not in ('placidus','whole','equal') or zodiac not in ('tropical','sidereal_lahiri'):
        raise ValueError('Unsupported house or zodiac setting.')
    # Preserve the comparison marker only on the legacy profile, never import it.
    return ({'label':label.strip(), 'birth':result_birth,
             'default_house_system':hs, 'default_zodiac':zodiac}, resolved)


def list_profiles(root):
    with LOCK:
        data = read_library(root)
        return {'active_id': data['active_id'], 'profiles': data['profiles']}


def get_active_profile(root):
    data = read_library(root)
    return next(p for p in data['profiles'] if p['id']==data['active_id'])


def create_profile(root, obj):
    clean, resolved = validate_profile(obj)
    with LOCK:
        data = read_library(root)
        if len(data['profiles']) >= MAX_PROFILES:
            raise ValueError('Profile library is full (60 charts). Export or remove one first.')
        item = dict(clean, id='chart_'+uuid.uuid4().hex[:16])
        data['profiles'].append(item)
        data['active_id']=item['id']
        _atomic_write(root,data)
    return {'profile':item, 'active_id':item['id'], 'resolved_utc':resolved.isoformat()}


def switch_profile(root, profile_id):
    if not isinstance(profile_id,str) or not ID_RE.fullmatch(profile_id):
        raise ValueError('Invalid profile ID.')
    with LOCK:
        data=read_library(root)
        if not any(p['id']==profile_id for p in data['profiles']):
            raise ValueError('Chart not found.')
        data['active_id']=profile_id
        _atomic_write(root,data)
        item=next(p for p in data['profiles'] if p['id']==profile_id)
        return {'active_id':profile_id, 'profile':item}


def update_profile(root, profile_id, obj):
    clean, resolved = validate_profile(obj)
    with LOCK:
        data=read_library(root)
        item=next((p for p in data['profiles'] if p['id']==profile_id),None)
        if item is None:
            raise ValueError('Chart not found.')
        new = dict(clean,id=profile_id)
        if item.get('reference_pdf'):
            # Do not compare an edited original profile with a the optional local PDF reference.
            legacy = _default_entry(root)['birth']
            if (new['birth'].get('date') == legacy.get('date') and
                new['birth'].get('time') == legacy.get('time') and
                new['birth'].get('timezone') == legacy.get('timezone') and
                abs(new['birth']['latitude'] - legacy['latitude']) < .00005 and
                abs(new['birth']['longitude'] - legacy['longitude']) < .00005):
                new['reference_pdf'] = True
        data['profiles']=[new if p['id']==profile_id else p for p in data['profiles']]
        _atomic_write(root,data)
    return {'profile':new, 'active_id':data['active_id'], 'resolved_utc':resolved.isoformat()}


def delete_profile(root, profile_id):
    with LOCK:
        data=read_library(root)
        if len(data['profiles'])==1:
            raise ValueError('Keep at least one birth chart in the library.')
        if not any(p['id']==profile_id for p in data['profiles']):
            raise ValueError('Chart not found.')
        data['profiles']=[p for p in data['profiles'] if p['id']!=profile_id]
        if data['active_id']==profile_id:
            data['active_id']=data['profiles'][0]['id']
        _atomic_write(root,data)
    return {'deleted':True,'active_id':data['active_id']}


def import_profile(root, obj):
    if not isinstance(obj,dict):
        raise ValueError('JSON must be an object.')
    if obj.get('format')=='astral-sentinel-birth-profile' and obj.get('version') == 1:
        item=obj.get('profile')
    elif 'birth_profile' in obj:
        item=obj['birth_profile']  # Existing AI exports may be imported as a new profile.
    else:
        raise ValueError('Not an Astral Sentinel profile JSON. Use an exported profile or an AI export with birth_profile.')
    return create_profile(root,item)


def export_profile(root, profile_id):
    data=read_library(root)
    item=next((p for p in data['profiles'] if p['id']==profile_id),None)
    if item is None:
        raise ValueError('Chart not found.')
    profile={k:v for k,v in item.items() if k not in ('id','reference_pdf')}
    return {'format':'astral-sentinel-birth-profile','version':1,'profile':profile,
            'description':'Input birth details only. Chart positions are recalculated on import.'}
