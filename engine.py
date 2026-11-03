"""Astral Sentinel transit engine.

Copyright (c) 2026 Astral Sentinel contributors.
SPDX-License-Identifier: AGPL-3.0-or-later

Positions are astronomy; interpretations and the pressure index are
configurable astrological conventions, not physical threat predictions.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from profile_manager import get_active_profile, birth_utc
from functools import lru_cache
import json
import math
from pathlib import Path
import threading

import swisseph as swe

ROOT = Path(__file__).resolve().parent
LOCK = threading.RLock()  # Swiss Ephemeris has global sidereal settings
SIGN_NAMES = ('Aries','Taurus','Gemini','Cancer','Leo','Virgo','Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces')
SIGN_SYMBOLS = ('♈','♉','♊','♋','♌','♍','♎','♏','♐','♑','♒','♓')
PLANETS = (
 ('Sun',swe.SUN,'☉'),('Moon',swe.MOON,'☾'),('Mercury',swe.MERCURY,'☿'),
 ('Venus',swe.VENUS,'♀'),('Mars',swe.MARS,'♂'),('Jupiter',swe.JUPITER,'♃'),
 ('Saturn',swe.SATURN,'♄'),('Uranus',swe.URANUS,'♅'),
 ('Neptune',swe.NEPTUNE,'♆'),('Pluto',swe.PLUTO,'♇')
)
ASPECTS = (
 ('conjunction','☌',0,5.0,'mixed'),('sextile','⚹',60,3.0,'support'),
 ('square','□',90,4.0,'tension'),('trine','△',120,4.0,'support'),
 ('opposition','☍',180,4.0,'tension')
)
WEIGHTS = {'Sun':1.15,'Moon':1.05,'Mercury':0.80,'Venus':0.95,'Mars':1.20,'Jupiter':1.20,'Saturn':1.55,'Uranus':1.20,'Neptune':1.10,'Pluto':1.45}
TARGET_WEIGHTS = {'Sun':1.2,'Moon':1.2,'Ascendant':1.2,'Midheaven':1.2,'Mercury':0.85,'Venus':1.,'Mars':1.,'Jupiter':.85,'Saturn':1.1,'Uranus':.85,'Neptune':.85,'Pluto':1.}
HOUSES = {'placidus':'P','whole':'W','equal':'E'}
HOUSE_METHODS = {'longitude', 'spatial'}  # Conventional cusp-based vs 3D house position
ZODIACS = {'tropical':None,'sidereal_lahiri':swe.SIDM_LAHIRI}
NODE_MODES={'mean':swe.MEAN_NODE,'true':swe.TRUE_NODE}
LILITH_MODES={'mean':swe.MEAN_APOG,'osculating':swe.OSCU_APOG}
AUX_DESCRIPTIONS={
 'North Node':'Ascending intersection of the Moon’s orbit with the ecliptic.',
 'South Node':'Descending intersection, 180° opposite the North Node.',
 'Black Moon Lilith':'Geocentric lunar apogee (not an asteroid or physical planet).',
 'Part of Fortune':'Calculated natal point using Ascendant, Moon and Sun; day/night sect formula.',
 'Vertex':'Calculated natal angle at the western intersection of the prime vertical.',
 'Chiron':'Centaur minor planet (2060 Chiron); calculated using Swiss asteroid ephemeris data.'
}
# Generic demo for fresh installations. No real person's birth data is bundled.
DEFAULT_PROFILE = {
 'label':'DEMO CHART - CREATE YOUR OWN',
 'birth':{'date':'2000-01-01','time':'12:00','timezone':'Europe/London',
          'latitude':51.5074,'longitude':-0.1278,'location_label':'London, GB (example coordinates)'},
 'default_house_system':'placidus','default_zodiac':'tropical'
}


def _reference_for(person):
    """Optional per-person reference kept outside distributable source code.

    A mismatch never overwrites entered birth details. Compare only against
    the exact birth record to which the reference belongs.
    """
    path = ROOT/'data'/'reference_chart.json'
    if not person.get('reference_pdf') or not path.is_file():
        return None
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
        birth=data['birth_key'];actual=person['birth']
        if not all(actual.get(k)==birth.get(k) for k in ('date','time','timezone')):
            return None
        if not all(abs(float(actual[k])-float(birth[k]))<.00005 for k in ('latitude','longitude')):
            return None
        return data
    except (ValueError, KeyError, TypeError, OSError):
        return None


def profile():
    # First-time upgrade preserves the legacy data/profile.json without modification.
    return get_active_profile(ROOT)


def jd_from_utc(dt):
    dt=dt.astimezone(timezone.utc)
    hour=(dt.hour+dt.minute/60+dt.second/3600+dt.microsecond/3_600_000_000)
    return swe.julday(dt.year,dt.month,dt.day,hour)


def now_utc():
    return datetime.now(timezone.utc)


def parse_datetime(raw):
    if not raw:
        return now_utc()
    dt=datetime.fromisoformat(str(raw).replace('Z','+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Datetime must include an explicit UTC offset')
    if not (1900 <= dt.year <= 2100):
        raise ValueError('Date out of supported app range (1900–2100)')
    return dt.astimezone(timezone.utc)


def natal_birth_dt(info):
    # Uses the recorded historical IANA time-zone rules, including explicit fold
    # when the local clock time occurred twice during a fall-back transition.
    return birth_utc(info['birth'])


def pos_obj(name, glyph, values):
    longitude=float(values[0])%360
    sign=int(longitude//30)
    return {'name':name,'glyph':glyph,'longitude':round(longitude,7),
            'latitude':round(values[1],7), 'distance_au':round(values[2],8),
            'speed_deg_day':round(values[3],8), 'retrograde':values[3]<0,
            'sign':SIGN_NAMES[sign], 'sign_glyph':SIGN_SYMBOLS[sign],
            'degree_in_sign':round(longitude%30,5)}


def planet_positions(jd,zodiac='tropical'):
    flags=swe.FLG_MOSEPH | swe.FLG_SPEED
    if zodiac=='sidereal_lahiri':
        swe.set_sid_mode(swe.SIDM_LAHIRI,0,0)
        flags |= swe.FLG_SIDEREAL
    return [pos_obj(name,glyph,swe.calc_ut(jd,pid,flags)[0]) for name,pid,glyph in PLANETS]


def auxiliary_positions(jd,zodiac='tropical',node_mode='mean',lilith_mode='mean',include_chiron=True):
    """Astronomical lunar points and optional minor planet; never fabricate data."""
    if node_mode not in NODE_MODES or lilith_mode not in LILITH_MODES:
        raise ValueError('Unsupported lunar point method')
    flags=swe.FLG_MOSEPH|swe.FLG_SPEED
    if zodiac=='sidereal_lahiri':
        swe.set_sid_mode(swe.SIDM_LAHIRI,0,0)
        flags|=swe.FLG_SIDEREAL
    n=pos_obj('North Node','☊',swe.calc_ut(jd,NODE_MODES[node_mode],flags)[0])
    n.update(kind='lunar_node', method=node_mode, definition=AUX_DESCRIPTIONS['North Node'])
    s=pos_obj('South Node','☋',( (n['longitude']+180)%360, 0.0, n['distance_au'], n['speed_deg_day']))
    s.update(kind='lunar_node',method=node_mode,derived_from='North Node + 180°',definition=AUX_DESCRIPTIONS['South Node'])
    l=pos_obj('Black Moon Lilith','⚸',swe.calc_ut(jd,LILITH_MODES[lilith_mode],flags)[0])
    l.update(kind='lunar_apogee',method=lilith_mode,definition=AUX_DESCRIPTIONS['Black Moon Lilith'])
    points=[n,s,l]
    unavailable=[]
    if include_chiron:
        asteroid_file=ROOT/'ephe'/'seas_18.se1'
        if asteroid_file.is_file():
            try:
                swe.set_ephe_path(str(asteroid_file.parent))
                chiron=pos_obj('Chiron','⚷',swe.calc_ut(jd,swe.CHIRON,((flags & ~swe.FLG_MOSEPH)|swe.FLG_SWIEPH))[0])
                chiron.update(kind='centaur',method='Swiss asteroid ephemeris',definition=AUX_DESCRIPTIONS['Chiron'])
                points.append(chiron)
            except swe.Error as exc:
                unavailable.append({'name':'Chiron','reason':'Swiss Ephemeris asteroid calculation failed: '+str(exc)})
        else:
            unavailable.append({'name':'Chiron','reason':'Optional ephe/seas_18.se1 asteroid file not installed.'})
    return points,unavailable


def natal_special_points(jd,person,positions,angles,ascmc,zodiac):
    """Compute nonphysical natal points; no transit Fortune/Vertex is implied."""
    sun=next(p for p in positions if p['name']=='Sun')
    moon=next(p for p in positions if p['name']=='Moon')
    b=person['birth']
    # The true solar altitude determines diurnal/nocturnal sect independently
    # of house-system and ecliptic coordinate assignment conventions.
    tropical_sun=pos_obj('Sun','☉',swe.calc_ut(jd,swe.SUN,swe.FLG_MOSEPH|swe.FLG_SPEED)[0])
    alt=swe.azalt(jd,swe.ECL2HOR,(b['longitude'],b['latitude'],0),0,15,
                  (tropical_sun['longitude'],tropical_sun['latitude'],tropical_sun['distance_au']))[1]
    daytime=alt>=0
    fortune_lon=(angles['Ascendant']+(moon['longitude']-sun['longitude'] if daytime else sun['longitude']-moon['longitude']))%360
    fortune=pos_obj('Part of Fortune','⊗',(fortune_lon,0,0,0))
    fortune.update(kind='calculated_natal',method='diurnal' if daytime else 'nocturnal',
                   definition=AUX_DESCRIPTIONS['Part of Fortune'],speed_deg_day=None,retrograde=None)
    vertex=pos_obj('Vertex','Vx',(ascmc[3]%360,0,0,0))
    vertex.update(kind='calculated_natal',method='Swiss Ephemeris Vertex (houses_ex)',
                  definition=AUX_DESCRIPTIONS['Vertex'],speed_deg_day=None,retrograde=None)
    return [fortune,vertex]


def heliocentric_positions(jd):
    # The Sun is the origin. The Moon remains a separate geocentric symbol in map UI.
    flags=swe.FLG_MOSEPH|swe.FLG_SPEED|swe.FLG_HELCTR
    entries=[]
    for name,pid,glyph in PLANETS:
        if name in ('Sun','Moon'):
            continue
        entries.append(pos_obj(name,glyph,swe.calc_ut(jd,pid,flags)[0]))
    entries.append(pos_obj('Earth','⊕',swe.calc_ut(jd,swe.EARTH,flags)[0]))
    return entries


def norm_diff(a,b):
    return (a-b+180)%360-180


def angular_separation(a,b):
    return abs(norm_diff(a,b))


def closest_aspect(a,b,orb_scale=1.0):
    delta=angular_separation(a,b)
    choices=[]
    for name,glyph,angle,max_orb,kind in ASPECTS:
        orb=abs(delta-angle)
        if orb<=max_orb*orb_scale:
            choices.append((orb/max_orb, name,glyph,angle,max_orb,kind,orb))
    if not choices: return None
    _,name,glyph,angle,max_orb,kind,orb=min(choices)
    return {'type':name,'symbol':glyph,'angle':angle,'orb':round(orb,4),
            'max_orb':max_orb,'kind':kind}


def house_for_planet(planet,cusps,angles,house_system,geo_lat,jd,house_method="longitude"):
    lon=planet['longitude']
    if house_system=='whole':
        base=(math.floor(angles['Ascendant']/30)*30)%360
        return int(((lon-base)%360)//30)+1
    if house_system=='equal':
        return int(((lon-angles['Ascendant'])%360)//30)+1
    # Most chart wheels assign planets by zodiacal longitude between house cusps.
    # The alternative latitude-aware 3D house position is kept as an explicit option.
    if house_method == 'longitude':
        return house_from_cusps(lon,cusps)
    # 3D house position accounts for the planet's ecliptic latitude.
    eps=swe.calc_ut(jd,swe.ECL_NUT,swe.FLG_MOSEPH)[0][0]
    armc=angles['ARMC']
    try:
        hp=swe.house_pos(armc,geo_lat,eps,(lon,planet['latitude']),b'P')
        return min(12,max(1,int(math.floor(hp))))
    except swe.Error:
        return house_from_cusps(lon,cusps)


def house_from_cusps(lon,cusps):
    for i in range(12):
        a=cusps[i]; b=cusps[(i+1)%12]
        if (lon-a)%360 < (b-a)%360: return i+1
    return 1


def chart_at(dt,person,house_system,zodiac,house_method="longitude",node_mode='mean',lilith_mode='mean'):
    if house_method not in HOUSE_METHODS: raise ValueError('Unsupported house placement method')
    b=person['birth']; jd=jd_from_utc(dt)
    positions=planet_positions(jd,zodiac)
    hs=HOUSES[house_system].encode('ascii')
    flags=swe.FLG_SIDEREAL if zodiac=='sidereal_lahiri' else 0
    try:
        raw_cusps,ascmc=swe.houses_ex(jd,b['latitude'],b['longitude'],hs,flags)
    except swe.Error as exc:
        if house_system=='placidus':
            raise ValueError('Placidus houses could not be calculated at this latitude. Try Whole Sign or Equal House.') from exc
        raise ValueError('House calculation unavailable for these birth coordinates.') from exc
    # pyswisseph 2.10.3.2 returns 12 cusps; pysweph 2.10.3.6 returns
    # 13 cusps with a dummy element at index 0 (1-indexed C API parity).
    # Normalize both to 12 entries indexed 0..11 for the rest of the engine.
    if len(raw_cusps) == 12:
        cusp=list(raw_cusps)
    elif len(raw_cusps) == 13:
        cusp=list(raw_cusps[1:])
    else:
        raise RuntimeError(f'Unsupported Swiss Ephemeris house cusp format: {len(raw_cusps)}')
    angles={'Ascendant':round(ascmc[0]%360,7),'Midheaven':round(ascmc[1]%360,7),
            'ARMC':round(ascmc[2]%360,7)}
    if house_system=='whole':
        start=int(angles['Ascendant']//30)*30
        cusp=[(start+30*i)%360 for i in range(12)]
    if house_system=='equal':
        start=angles['Ascendant']
        cusp=[(start+30*i)%360 for i in range(12)]
    for p in positions:
        p['house']=house_for_planet(p,cusp,angles,house_system,b['latitude'],jd,house_method)
    aux,unavailable=auxiliary_positions(jd,zodiac,node_mode,lilith_mode)
    aux+=natal_special_points(jd,person,positions,angles,ascmc,zodiac)
    for p in aux:
        p['house']=house_for_planet(p,cusp,angles,house_system,b['latitude'],jd,
                                    house_method if p['kind'] in ('lunar_node','lunar_apogee','centaur') else 'longitude')
    return {'positions':positions,'auxiliary_points':aux,'auxiliary_unavailable':unavailable,'angles':angles,
            'cusps':[round(n%360,7) for n in cusp],
            'house_system':house_system,'house_method':house_method,'zodiac':zodiac,'timestamp':dt.isoformat()}


def natal_verification(natal,person):
    # The revised PDF belongs to the *original* user profile only.
    reported=_reference_for(person)
    if reported is None:
        return {'status':'unavailable','message':'No external PDF reference is attached to this chart. Birth details were independently recalculated from the entered time, location and historical time zone.','differences':[]}
    # Compare PDF claims only in matching tropical Placidus mode. The reference
    # is intentionally NOT used to change the user's recorded birth details.
    if natal['zodiac']!='tropical' or natal['house_system']!='placidus':
        return {'status':'unavailable','message':'Use Tropical + Placidus to compare to the revised PDF.'}
    diffs=[]
    for name in ('Ascendant','Midheaven'):
        calc=natal['angles'][name]; expected=reported[name]
        if abs(norm_diff(calc,expected))>0.25:
            diffs.append({'item':name,'reported':round(expected,3),
                          'calculated':round(calc,3),'difference_degrees':round(abs(norm_diff(calc,expected)),3),
                          'message':f'PDF reports {name} at {expected:.2f}°, calculation gives {calc:.2f}°.'})
    moon=next(p for p in natal['positions'] if p['name']=='Moon')
    if abs(norm_diff(moon['longitude'],reported['Moon']))>0.25:
        diffs.append({'item':'Moon longitude','reported':round(reported['Moon'],3),
                      'calculated':round(moon['longitude'],3),
                      'difference_degrees':round(abs(norm_diff(moon['longitude'],reported['Moon'])),3),
                      'message':f"PDF reports Moon at {reported['Moon']:.3f}°, calculated Moon is {moon['longitude']:.3f}°."})
    for p in natal['positions']:
        original=reported['houses'].get(p['name'])
        if original is not None and original!=p['house']:
            diffs.append({'item':p['name']+' house','reported':original,
                          'calculated':p['house'],
                          'message':f"PDF labels {p['name']} as house {original}; calculated house is {p['house']}."})
    tzdt=natal_birth_dt(person)
    details={'time_zone':person['birth']['timezone'],
             'resolved_utc':tzdt.isoformat(),
             'utc_offset':tzdt.astimezone(ZoneInfo(person['birth']['timezone'])).strftime('%z'),
             'house_method':natal['house_method']}
    # A one-hour discrepancy is present in the supplied reference: diagnose it,
    # but do not treat the offset comparison as a proposed correction to birth time.
    if any(d['item'] in ('Ascendant','Midheaven','Moon longitude') for d in diffs):
        earlier=chart_at(tzdt-timedelta(hours=1),person,'placidus','tropical',natal['house_method'])
        angles_agree=(abs(norm_diff(earlier['angles']['Ascendant'],reported['Ascendant']))<.25 and
                      abs(norm_diff(earlier['angles']['Midheaven'],reported['Midheaven']))<.25)
        prior_moon=next(p['longitude'] for p in earlier['positions'] if p['name']=='Moon')
        if angles_agree and abs(norm_diff(prior_moon,reported['Moon']))<.25:
            details['one_hour_offset_match']={
                'alternate_utc':earlier['timestamp'],
                'alternate_ascendant':round(earlier['angles']['Ascendant'],4),
                'alternate_midheaven':round(earlier['angles']['Midheaven'],4),
                'alternate_moon':round(prior_moon,4),
                'message':('The PDF angles and Moon closely match calculations one hour earlier '
                           'than the UTC instant implied by the recorded local birth time. '
                           'This is consistent with a historical DST/time-zone conversion mismatch '
                           'in the PDF. The entered local birth time has NOT been changed.')}
    return {'status':'review' if diffs else 'match', 'differences':diffs,
            'message':f'{len(diffs)} differences found against the revised PDF.' if diffs else 'No differences found.',
            'source':reported['source'],
            'method':'Recalculated from the recorded local birth date/time, coordinates, and historical IANA time zone.',
            'time_diagnostic':details}


def aspect_condition(transit_name,kind):
    if kind!='mixed':return kind
    if transit_name in ('Mars','Saturn','Pluto','Neptune','Uranus'): return 'tension'
    if transit_name in ('Jupiter','Venus'):return 'support'
    return 'mixed'


def aspect_phase(transit_lon, speed_deg_day, natal_lon, target_angle, orb):
    """Classify approach/recession using the instantaneous angular motion.

    Sample 5 minutes on either side with the ephemeris-reported instantaneous
    speed, rather than 12 hours *ahead*, which can cross exactness for the Moon.
    The angle-based result is local to the requested instant.
    """
    if orb < 0.00001:
        return 'exact'
    dt_days=5/(24*60)
    before=(transit_lon-speed_deg_day*dt_days)%360
    after=(transit_lon+speed_deg_day*dt_days)%360
    orb_before=abs(angular_separation(before,natal_lon)-target_angle)
    orb_after=abs(angular_separation(after,natal_lon)-target_angle)
    if abs(orb_after-orb_before)<1e-9:
        return 'stationary'
    return 'applying' if orb_after<orb_before else 'separating'


def list_transit_aspects(transits,natal):
    items=[]
    targets=natal['positions']+[
      {'name':'Ascendant','glyph':'AC','longitude':natal['angles']['Ascendant'],'house':1},
      {'name':'Midheaven','glyph':'MC','longitude':natal['angles']['Midheaven'],'house':10}
    ]
    for tp in transits:
        for np in targets:
            match=closest_aspect(tp['longitude'],np['longitude'])
            if not match:continue
            nature=aspect_condition(tp['name'],match['kind'])
            strength=max(0,1-match['orb']/match['max_orb'])
            weight=WEIGHTS[tp['name']]*TARGET_WEIGHTS.get(np['name'],1)*strength
            value = round((1 if nature=='support' else -1 if nature=='tension' else 0)*weight,4)
            phase=aspect_phase(tp['longitude'],tp['speed_deg_day'],np['longitude'],match['angle'],match['orb'])
            applying=phase=='applying'
            items.append({**match,'transit':tp['name'],'transit_glyph':tp['glyph'],
                          'natal':np['name'],'natal_glyph':np['glyph'],
                          'house':np.get('house'), 'applying':applying, 'phase':phase,
                          'nature':nature,'strength':round(strength,4),
                          'weight':round(weight,4),'value':value})
    items.sort(key=lambda item:(-item['weight'],item['orb']))
    return items


def list_sky_aspects(transits):
    items=[]
    for i,a in enumerate(transits):
        for b in transits[i+1:]:
            match=closest_aspect(a['longitude'],b['longitude'],0.75)
            if match:
                items.append({**match,'from':a['name'],'to':b['name'],
                              'nature':aspect_condition(a['name'],match['kind'])})
    return items



# Auxiliary aspect overlay is deliberately separate from the scored planetary
# aspects. Tight, user-selectable orbs help keep the hologram legible.
def auxiliary_aspect_match(a, b, orb_limit=2.0):
    """Return an ordinary major-aspect geometry with a strict auxiliary orb."""
    separation = angular_separation(a, b)
    options = []
    for name, glyph, angle, _standard_orb, kind in ASPECTS:
        orb = abs(separation - angle)
        if orb <= orb_limit:
            options.append((orb, name, glyph, angle, kind))
    if not options:
        return None
    orb, name, glyph, angle, kind = min(options)
    return {'type': name, 'symbol': glyph, 'angle': angle,
            'orb': round(orb, 4), 'max_orb': float(orb_limit),
            'kind': kind, 'nature': kind, 'strength': round(max(0, 1-orb/orb_limit), 4)}


def list_auxiliary_aspects(transits, natal, auxiliary_transits, orb_limit=2.0):
    """Live auxiliary -> natal targets, plus planet -> natal auxiliary targets.

    Both natal lunar points and natal-only Fortune/Vertex are eligible targets.
    These are geometric observations, not additions to the pressure model.
    """
    natal_planets = natal['positions'] + [
        {'name': 'Ascendant', 'glyph': 'AC', 'longitude': natal['angles']['Ascendant'], 'house': 1},
        {'name': 'Midheaven', 'glyph': 'MC', 'longitude': natal['angles']['Midheaven'], 'house': 10},
    ]
    natal_aux = natal.get('auxiliary_points', [])
    aspects = []
    for sources, targets, category in (
        (auxiliary_transits, natal_planets + natal_aux, 'auxiliary_to_natal'),
        (transits, natal_aux, 'planet_to_natal_auxiliary'),
    ):
        for src in sources:
            for dst in targets:
                match = auxiliary_aspect_match(src['longitude'], dst['longitude'], orb_limit)
                if not match:
                    continue
                phase = aspect_phase(src['longitude'], src['speed_deg_day'],
                                     dst['longitude'], match['angle'], match['orb'])
                aspects.append({**match, 'source': src['name'], 'target': dst['name'],
                                'source_scope': 'transit', 'target_scope': 'natal',
                                'source_auxiliary': category == 'auxiliary_to_natal',
                                'target_auxiliary': dst in natal_aux,
                                'source_glyph': src['glyph'], 'target_glyph': dst['glyph'],
                                'target_house': dst.get('house'), 'phase': phase,
                                'category': category, 'scored': False})
    aspects.sort(key=lambda a: (a['orb'], a['source'], a['target']))
    return aspects


def list_auxiliary_sky_aspects(transits, auxiliary_transits, orb_limit=2.0):
    """Live auxiliary points connected to ordinary live planets only.

    Excludes auxiliary-to-auxiliary sky connections, so the always-opposed
    lunar nodes do not create meaningless permanent aspect lines.
    """
    aspects = []
    for src in auxiliary_transits:
        for dst in transits:
            match = auxiliary_aspect_match(src['longitude'], dst['longitude'], orb_limit)
            if not match:
                continue
            phase = aspect_phase(src['longitude'],
                                 src['speed_deg_day']-dst['speed_deg_day'],
                                 dst['longitude'], match['angle'], match['orb'])
            aspects.append({**match, 'source': src['name'], 'target': dst['name'],
                            'source_scope': 'transit', 'target_scope': 'transit',
                            'source_auxiliary': True, 'target_auxiliary': False,
                            'source_glyph': src['glyph'], 'target_glyph': dst['glyph'],
                            'target_house': None, 'phase': phase,
                            'category': 'auxiliary_to_sky', 'scored': False})
    aspects.sort(key=lambda a: (a['orb'], a['source'], a['target']))
    return aspects

# Proposed qualitative priorities, NOT calibrated probabilities. Only transit-to-natal
# auxiliary alignments count. A 2 degree score orb is independent of display filters.
AUX_SCORING_WEIGHTS = {'North Node': .38, 'South Node': .38,
                       'Black Moon Lilith': .24, 'Part of Fortune': .24,
                       'Vertex': .12, 'Chiron': .38}
AUX_SCORING_ORB = 2.0


def auxiliary_influence(auxiliary_aspects, enabled=True):
    """Conservative, bounded secondary modifier; avoid mirrored nodal double-counting."""
    entries=[]
    seen=set()
    for a in sorted(auxiliary_aspects, key=lambda v: (v['orb'],v['source'],v['target'])):
        if a['orb'] > AUX_SCORING_ORB:
            continue
        source=a['source']; target=a['target']
        axis_source='Lunar Node Axis' if source in ('North Node','South Node') else source
        axis_target='Lunar Node Axis' if target in ('North Node','South Node') else target
        key=(axis_source,axis_target,a['category'])
        if key in seen:continue
        seen.add(key)
        point=source if a['source_auxiliary'] else target
        weight=AUX_SCORING_WEIGHTS.get(point,0)
        if not weight:continue
        kind=a['kind']
        # A conjunction isn't automatically good or bad. This is a deliberately
        # restrained starting policy, with neutral nodes/Vertex conjunctions.
        if kind=='mixed':
            kind=('support' if point=='Part of Fortune' else
                  'tension' if point in ('Black Moon Lilith','Chiron') else 'mixed')
        strength=max(0.,1.-a['orb']/AUX_SCORING_ORB)
        value=round(weight*strength*(1 if kind=='support' else -1 if kind=='tension' else 0),5)
        entries.append({'source':source,'target':target,'category':a['category'],
                        'type':a['type'],'orb':a['orb'],'nature':kind,
                        'value':value,'weight':weight,'axis_deduplicated':axis_source=='Lunar Node Axis' or axis_target=='Lunar Node Axis'})
    raw=sum(a['value'] for a in entries)
    modifier=round(-.65*math.tanh(raw/1.2),3) if enabled else 0.0
    return {'enabled':bool(enabled),'orb':AUX_SCORING_ORB,'weights':dict(AUX_SCORING_WEIGHTS),
            'entries':entries,'raw_signal':round(raw,4),'modifier':modifier,
            'max_abs_modifier':.65,'note':'Experimental, capped interpretive offset; nodal axis pairs counted once; transit-to-natal only. Neutral conjunctions do not change the score.'}


def combined_score(planet_score, influence):
    """Preserve original base score; append an optional transparent modifier."""
    result=dict(planet_score)
    base=planet_score['difficulty']
    effective=max(1,min(10,round(base+influence['modifier'],1)))
    result['difficulty']=effective
    result['status']=('CALM SECTOR' if effective<3 else 'FAVORABLE CONDITIONS' if effective<4.5 else
                      'SYSTEM NOMINAL' if effective<5.8 else 'ELEVATED PRESSURE' if effective<7.5 else
                      'STRUCTURAL STRESS' if effective<9 else 'CRITICAL ALIGNMENTS')
    result['planetary_baseline']=base
    result['auxiliary_modifier']=influence['modifier']
    result['auxiliary_enabled']=influence['enabled']
    result['method']='Astral Sentinel v0.2.2 interpretive planetary + optional auxiliary layer'
    result['formula']='base = planetary score formula; combined = clamp(round(base + capped auxiliary modifier, 1), 1, 10)'
    return result


def compute_score(aspects):
    # Deliberately simple, editable ASTROLOGICAL model, not predictive calibration.
    tension=sum(-a['value'] for a in aspects if a['value']<0)
    support=sum(a['value'] for a in aspects if a['value']>0)
    # Avoid crowding: diminishing returns for dozens of weak aspects.
    pressure=5.0 + 1.22*math.log1p(tension) - 1.10*math.log1p(support)
    score=max(1,min(10,round(pressure,1)))
    level = ('CALM SECTOR' if score<3 else 'FAVORABLE CONDITIONS' if score<4.5 else
             'SYSTEM NOMINAL' if score<5.8 else 'ELEVATED PRESSURE' if score<7.5 else
             'STRUCTURAL STRESS' if score<9 else 'CRITICAL ALIGNMENTS')
    return {'difficulty':score,'status':level,'tension':round(tension,3),
            'support':round(support,3), 'method':'Astral Sentinel v0.1 interpretive weighted aspects',
            'formula':'clamp(5 + 1.22*ln(1+tension) - 1.10*ln(1+support), 1, 10)',
            'disclaimer':'Interpretive astrological indicator, not a prediction of events, harm, or safety.'}


def planet_status(transits,aspects):
    result=[]
    for p in transits:
        relevant=[a for a in aspects if a['transit']==p['name']]
        signed=sum(a['value'] for a in relevant)
        status='support' if signed>.35 else 'tension' if signed<-.35 else 'neutral'
        result.append({'name':p['name'],'glyph':p['glyph'],'longitude':p['longitude'],
                       'value':round(signed,2),'status':status,
                       'aspects':len(relevant),'retrograde':p['retrograde']})
    return result


# Interpretive areas associated with natal houses. These are labels for
# reviewing aspect patterns, not claims that an event will occur in an area.
HOUSE_AREAS = {
    1: 'Identity & Personal Direction',
    2: 'Finances & Resources',
    3: 'Communication & Learning',
    4: 'Family & Home',
    5: 'Creativity & Recreation',
    6: 'Work & Daily Routines',
    7: 'Relationships',
    8: 'Shared Resources & Commitments',
    9: 'Education & Travel',
    10: 'Career & Public Life',
    11: 'Friends & Community',
    12: 'Rest & Privacy',
}
# Target planets provide more specific topics in addition to the natal house.
NATAL_TARGET_AREAS = {
    'Sun': 'Identity & Personal Direction',
    'Moon': 'Family & Home',
    'Mercury': 'Communication & Learning',
    'Venus': 'Relationships',
    'Mars': 'Work & Daily Routines',
    'Uranus': 'Technology & Change',
    'Ascendant': 'Identity & Personal Direction',
    'Midheaven': 'Career & Public Life',
    'Part of Fortune': 'Finances & Resources',
    'Vertex': 'Relationships',
    'Chiron': 'Health & Recovery',
    'Black Moon Lilith': 'Autonomy & Boundaries',
    'North Node': 'Identity & Personal Direction',
    'South Node': 'Identity & Personal Direction',
}
# Transiting bodies are a minor thematic hint, never the primary house signal.
TRANSIT_AREAS = {
    'Mercury': 'Communication & Learning',
    'Venus': 'Relationships',
    'Moon': 'Family & Home',
    'Uranus': 'Technology & Change',
    'Chiron': 'Health & Recovery',
    'Black Moon Lilith': 'Autonomy & Boundaries',
}


def affected_areas(aspects, nature, auxiliary_scoring=None, natal=None, limit=4):
    """Rank areas by existing aspect weights and natal-house relevance.

    Main planetary aspects drive the order. Enabled, already-deduplicated
    auxiliary scoring entries can add a smaller signal. We never count a
    sky-to-sky aspect or equate topic ranks with real-world probabilities.
    """
    scores = {}
    def add(name, amount):
        if name and amount > 0:
            scores[name] = scores.get(name, 0.) + amount
    def apply(src, dst, house, magnitude, auxiliary=False):
        if magnitude <= 0:
            return
        scale = 0.55 if auxiliary else 1.0
        add(HOUSE_AREAS.get(house), magnitude * scale)
        target_theme = NATAL_TARGET_AREAS.get(dst)
        if target_theme != HOUSE_AREAS.get(house):
            add(target_theme, magnitude * scale * .6)
        source_theme = TRANSIT_AREAS.get(src)
        if source_theme not in (HOUSE_AREAS.get(house), target_theme):
            add(source_theme, magnitude * scale * .25)

    for aspect in aspects:
        if aspect.get('nature') != nature:
            continue
        apply(aspect['transit'], aspect['natal'], aspect.get('house'),
              abs(float(aspect.get('value', 0))))

    if auxiliary_scoring and auxiliary_scoring.get('enabled') and natal:
        target_houses = {p['name']: p['house'] for p in
                          natal.get('positions', []) + natal.get('auxiliary_points', [])}
        target_houses.update({'Ascendant': 1, 'Midheaven': 10})
        for entry in auxiliary_scoring.get('entries', []):
            if entry.get('nature') != nature:
                continue
            # All scoring entries are transit-to-natal. Do not add separate
            # South Node contributions when the scoring axis is deduplicated.
            apply(entry['source'], entry['target'], target_houses.get(entry['target']),
                  abs(float(entry.get('value', 0))), auxiliary=True)
    return [area for area, _score in
            sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:limit]]


def advice(aspects, score, auxiliary_scoring=None, natal=None):
    if not aspects:
        return [{'title':'OPEN SKY','kind':'neutral',
                 'text':'Few close major natal transits in the selected orb ranges.'}]
    hot=next((a for a in aspects if a['nature']=='tension'),None)
    good=next((a for a in aspects if a['nature']=='support'),None)
    notices=[]
    if hot:
        domain=('career and public roles' if hot['natal']=='Midheaven' or hot['house']==10 else
                'home and foundations' if hot['house']==4 else
                'work and routines' if hot['house']==6 else
                'personal priorities' if hot['natal']=='Sun' else
                'relationships' if hot['house']==7 else
                'the highlighted natal area')
        notices.append({'title':'STRUCTURAL STRESS WARNING', 'kind':'tension',
          'text':f"{hot['transit']} {hot['symbol']} natal {hot['natal']} ({hot['orb']:.2f}° orb). In traditional interpretation, use extra care with {domain}.",
          'areas':affected_areas(aspects,'tension',auxiliary_scoring,natal)})
    if good:
        notices.append({'title':'OPPORTUNITY WINDOW DETECTED','kind':'support',
          'text':f"{good['transit']} {good['symbol']} natal {good['natal']} ({good['orb']:.2f}° orb). Favor constructive work and support.",
          'areas':affected_areas(aspects,'support',auxiliary_scoring,natal)})
    notices.append({'title':'TACTICAL ADVISORY','kind':'neutral','text':
       'Interpretive planning cue: prioritize what you can control. A red transit is not a literal danger alert.' if score['difficulty']>=6 else
       'Interpretive planning cue: use the lighter period for useful, sustainable progress.'})
    return notices


def snapshot(dt=None,house_system='placidus',zodiac='tropical',include_sky=True,house_method='longitude',node_mode='mean',lilith_mode='mean',aux_orb=2.0,aux_scoring=True):
    if house_system not in HOUSES:raise ValueError('Unsupported house system')
    if zodiac not in ZODIACS:raise ValueError('Unsupported zodiac system')
    if house_method not in HOUSE_METHODS:raise ValueError('Unsupported house placement method')
    if node_mode not in NODE_MODES or lilith_mode not in LILITH_MODES:
        raise ValueError('Unsupported lunar point method')
    aux_orb=float(aux_orb)
    if not math.isfinite(aux_orb) or not (0.5 <= aux_orb <= 3.0):
        raise ValueError('Auxiliary aspect orb must be between 0.5° and 3°')
    dt=dt or now_utc()
    person=profile()
    with LOCK:
        natal=chart_at(natal_birth_dt(person),person,house_system,zodiac,house_method,node_mode,lilith_mode)
        transits=planet_positions(jd_from_utc(dt),zodiac)
        aux_transits,aux_unavailable=auxiliary_positions(jd_from_utc(dt),zodiac,node_mode,lilith_mode)

        heliocentric=heliocentric_positions(jd_from_utc(dt)) if include_sky else []
        aspect_list=list_transit_aspects(transits,natal)
        base_score=compute_score(aspect_list)
        aux_aspects=list_auxiliary_aspects(transits,natal,aux_transits,aux_orb)
        scoring_aspects=aux_aspects if aux_orb>=AUX_SCORING_ORB else list_auxiliary_aspects(transits,natal,aux_transits,AUX_SCORING_ORB)
        influence=auxiliary_influence(scoring_aspects,aux_scoring)
        score=combined_score(base_score,influence)
        aux_sky_aspects=list_auxiliary_sky_aspects(transits,aux_transits,aux_orb) if include_sky else []
        return {'app':'Astral Sentinel','version':'1.0.0','at_utc':dt.isoformat(),
                'birth_profile':person,'natal':natal,'transits':transits,'auxiliary_transits':aux_transits,'auxiliary_unavailable':aux_unavailable,'heliocentric':heliocentric,
                'transit_to_natal_aspects':aspect_list,'sky_aspects':list_sky_aspects(transits) if include_sky else [],
                'auxiliary_aspects':aux_aspects,'auxiliary_sky_aspects':aux_sky_aspects,
                'score':score,'auxiliary_scoring':influence,'planet_status':planet_status(transits,aspect_list),
                'notices':advice(aspect_list,score,influence,natal),
                'verification':natal_verification(natal,person),
                'ephemeris':{'engine':'Swiss Ephemeris / Moshier + Swiss asteroid ephemeris',
                             'version':swe.version, 'mode':'Moshier for planets and lunar points; bundled Swiss asteroid ephemeris for Chiron',
                             'geocentric':'Tropical or Lahiri sidereal ecliptic longitude for transits and natal chart',
                             'heliocentric':'Physical heliocentric longitude (tropical) for Solar View'},
                'auxiliary_meta':{'node_mode':node_mode,'lilith_mode':lilith_mode,'aspect_orb':aux_orb,
                                  'aspect_categories':['auxiliary_to_natal','planet_to_natal_auxiliary','auxiliary_to_sky'],
                                  'aspects_scored':bool(aux_scoring),
                                  'scoring':'Opt-in/out capped auxiliary influence; tight 2° scoring orb independent of display orb; no sky-to-sky scoring.',
                                  'transits':'North Node, South Node, Black Moon Lilith and Chiron (if optional ephemeris file available).',
                                  'natal_only':'Part of Fortune and Vertex are calculated natal points; no live transit is inferred.'},
                'interpretation_note':'Scores/colors reflect adjustable astrological rules and are not objective hazard probabilities.'}


def forecast(start,days=30,house_system='placidus',zodiac='tropical',house_method='longitude',node_mode='mean',lilith_mode='mean',aux_scoring=True):
    if days not in (7,30,90):raise ValueError('days must be 7, 30, or 90')
    if house_system not in HOUSES or zodiac not in ZODIACS or house_method not in HOUSE_METHODS:
        raise ValueError('Unsupported chart configuration')
    person=profile()
    with LOCK:
        natal=chart_at(natal_birth_dt(person),person,house_system,zodiac,house_method,node_mode,lilith_mode)
        readings=[]
        interval_hours=3 if days==7 else 6 if days==30 else 12
        n=round(days*24/interval_hours)
        for i in range(n+1):
            d=start+timedelta(hours=interval_hours*i)
            tp=planet_positions(jd_from_utc(d),zodiac)
            asp=list_transit_aspects(tp,natal)
            base=compute_score(asp)
            if aux_scoring:
                aux,_=auxiliary_positions(jd_from_utc(d),zodiac,node_mode,lilith_mode)
                scored=list_auxiliary_aspects(tp,natal,aux,AUX_SCORING_ORB)
            else:
                scored=[]
            influence=auxiliary_influence(scored,aux_scoring)
            score=combined_score(base,influence)
            readings.append({'at_utc':d.isoformat(),'difficulty':score['difficulty'],
                             'planetary_baseline':base['difficulty'],'auxiliary_modifier':influence['modifier'],
                             'tension':score['tension'],'support':score['support']})
        lo=min(readings,key=lambda x:x['difficulty']);hi=max(readings,key=lambda x:x['difficulty'])
        # Important: these are sampled best/worst interpretive scores, not event predictions.
        return {'days':days,'start_utc':start.isoformat(),'house_system':house_system,
                'zodiac':zodiac,'house_method':house_method,'node_mode':node_mode,'lilith_mode':lilith_mode,'aux_scoring':bool(aux_scoring),'samples':readings,
                'lowest':lo,'highest':hi,'sampling_hours':interval_hours,
                'note':'Forecast is sampled every 3h (7 days), 6h (30 days), or 12h (90 days). Short peaks between samples may be missed; extrema are not event predictions.'}
