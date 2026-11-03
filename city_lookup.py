"""Offline starter city search, backed by bundled reference-city coordinates."""
from functools import lru_cache
from pathlib import Path
import json
import unicodedata

@lru_cache(maxsize=1)
def _entries():
    path=Path(__file__).resolve().parent/'data'/'city_catalog.json'
    return json.loads(path.read_text(encoding='utf-8'))['entries']

def _fold(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',text).casefold() if not unicodedata.combining(c))

def search_cities(query,limit=15):
    q=_fold(str(query or '').strip())
    if len(q)<2:
        return []
    if len(q)>100:
        raise ValueError('City search too long.')
    found=[]
    for item in _entries():
        name=_fold(item['name']);label=_fold(item['label']);tz=_fold(item['timezone'])
        if q == name:rank=0
        elif name.startswith(q):rank=1
        elif q in name:rank=2
        elif q in label or q in tz:rank=3
        else:continue
        found.append((rank,len(item['name']),item))
    found.sort(key=lambda x:(x[0],x[1],x[2]['label']))
    return [p for _,_,p in found[:limit]]
