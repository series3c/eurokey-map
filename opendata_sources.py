"""
Zusaetzliche Eurokey-Standorte aus amtlichen Open-Government-Data-Quellen
(Staedte Zuerich, Genf, Basel-Stadt, Luzern), ergaenzend zu OpenStreetMap.

Jede fetch_*-Funktion liefert eine Liste von dicts im selben Schema wie
die aus fetch_data.py stammenden OSM-Eintraege (siehe cleaned_data.append
dort), damit sie direkt gemergt werden koennen.
"""
import json
import re
import urllib.request
import xml.etree.ElementTree as ET

HEADERS = {'User-Agent': 'EurokeyFinderDACH-Pi/1.0 (contact: info@series3c.ch)'}


def lv95_to_wgs84(e, n):
    """Naeherungsformel swisstopo: LV95 (EPSG:2056) -> WGS84. Genauigkeit ~1m."""
    y = (e - 2600000) / 1000000
    x = (n - 1200000) / 1000000
    lon = 2.6779094 + 4.728982 * y + 0.791484 * y * x + 0.1306 * y * x**2 - 0.0436 * y**3
    lat = 16.9023892 + 3.238272 * x - 0.270978 * y**2 - 0.002528 * x**2 - 0.0447 * y**2 * x - 0.0140 * x**3
    lon = lon * 100 / 36
    lat = lat * 100 / 36
    return lat, lon


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _parse_charge(text):
    """Versucht einen Frankenbetrag wie 'Fr. 1.--' oder '1 CHF' aus Freitext zu lesen."""
    if not text:
        return ''
    m = re.search(r'Fr\.?\s*(\d+(?:[.,]\d+)?)', text)
    if m:
        return f"{m.group(1).replace(',', '.')} CHF"
    return ''


def fetch_zurich():
    """Staedt. Zuerich, Datensatz 'Zueri WC' (CC0), Layer Rollstuhl-WC."""
    url = ('https://www.ogd.stadt-zuerich.ch/wfs/geoportal/Zueri_WC'
           '?SERVICE=WFS&REQUEST=GetFeature&VERSION=1.1.0&TYPENAME=poi_zueriwc_rs_view')
    xml_bytes = _get(url)
    ns = {'gml': 'http://www.opengis.net/gml', 'qgs': 'http://www.qgis.org/gml'}
    root = ET.fromstring(xml_bytes)

    results = []
    for member in root.findall('.//qgs:poi_zueriwc_rs_view', ns):
        def field(tag):
            el = member.find(f'qgs:{tag}', ns)
            return (el.text or '').strip() if el is not None and el.text else ''

        bemerkung = field('bemerkung') or field('infrastruktur')
        if 'eurokey' not in bemerkung.lower():
            continue

        geom = member.find('qgs:geometry', ns)
        e, n = None, None
        if geom is not None:
            coords_el = geom.find('.//gml:coordinates', ns)
            pos_el = geom.find('.//gml:pos', ns)
            if coords_el is not None and coords_el.text:
                e_str, n_str = coords_el.text.strip().split(',')
                e, n = float(e_str), float(n_str)
            elif pos_el is not None and pos_el.text:
                e_str, n_str = pos_el.text.strip().split()
                e, n = float(e_str), float(n_str)
        if e is None or n is None:
            continue
        lat, lon = lv95_to_wgs84(e, n)

        gebuehren = field('gebuehren')
        if 'frei' in gebuehren.lower():
            fee = 'no'
        elif gebuehren:
            fee = 'yes'
        else:
            fee = ''

        poi_id = field('poi_id') or field('objectid')
        strasse = field('adresse') or field('strasse')
        plz = field('plz')
        ort = field('ort') or 'Zürich'
        address = ', '.join(p for p in [strasse, f"{plz} {ort}".strip()] if p)

        results.append({
            'id': f'zh_wc_{poi_id}',
            'osm_id': None,
            'osm_type': '',
            'lat': lat,
            'lon': lon,
            'name': field('name') or 'Eurokey WC',
            'operator': 'Stadt Zürich (Züri WC)',
            'address': address,
            'opening_hours': field('oeffnungsz'),
            'fee': fee,
            'charge': _parse_charge(gebuehren),
            'fee_centralkey': '',
            'level': '',
            'desc': bemerkung,
            'type': 'toilets',
            'source': 'opendata',
        })
    return results


def fetch_geneva():
    """Ville de Geneve, Datensatz 'WC publics'."""
    url = ('https://vector.sitg.ge.ch/arcgis/rest/services/VDG_WC_PUBLIC/FeatureServer/0/query'
           '?where=1%3D1&outFields=*&f=json')
    data = json.loads(_get(url))

    results = []
    for feat in data.get('features', []):
        attrs = feat.get('attributes', {})
        access = (attrs.get('ACCESSIBILITE') or '')
        if 'eurokey' not in access.lower():
            continue
        geom = feat.get('geometry') or {}
        if 'x' not in geom or 'y' not in geom:
            continue
        lat, lon = lv95_to_wgs84(geom['x'], geom['y'])

        address = attrs.get('ADRESSE') or ''
        quartier = attrs.get('QUARTIER') or ''
        address = ', '.join(p for p in [address, quartier, 'Genève'] if p)

        results.append({
            'id': f"ge_wc_{attrs.get('OBJECTID')}",
            'osm_id': None,
            'osm_type': '',
            'lat': lat,
            'lon': lon,
            'name': attrs.get('INTITULE') or 'Eurokey WC',
            'operator': 'Ville de Genève',
            'address': address,
            'opening_hours': attrs.get('OUVERTURE') or '',
            'fee': '',
            'charge': '',
            'fee_centralkey': '',
            'level': '',
            'desc': ', '.join(p for p in [access, attrs.get('REMARQUES') or ''] if p),
            'type': 'toilets',
            'source': 'opendata',
        })
    return results


def fetch_basel():
    """Kanton Basel-Stadt, Datensatz 'Sanitaere Anlagen'."""
    url = 'https://data.bs.ch/api/v2/catalog/datasets/100031/exports/geojson'
    data = json.loads(_get(url))

    results = []
    for feat in data.get('features', []):
        props = feat.get('properties', {})
        if props.get('eurokey') is not True:
            continue
        status = (props.get('status') or '').lower()
        if 'ausser betrieb' in status or 'geschlossen' in status:
            continue
        coords = (feat.get('geometry') or {}).get('coordinates')
        if not coords:
            continue
        lon, lat = coords[0], coords[1]

        strasse = props.get('strasse') or ''
        plz = props.get('plz') or ''
        ort = props.get('ort') or ''
        address = ', '.join(p for p in [strasse, f"{plz} {ort}".strip()] if p)

        gebuehr = props.get('gebuehr') or ''
        fee = 'no' if 'kostenlos' in gebuehr.lower() else ('yes' if gebuehr else '')

        results.append({
            'id': f"bs_wc_{props.get('id')}",
            'osm_id': None,
            'osm_type': '',
            'lat': lat,
            'lon': lon,
            'name': props.get('bezeichnung') or 'Eurokey WC',
            'operator': 'Kanton Basel-Stadt',
            'address': address,
            'opening_hours': '',
            'fee': fee,
            'charge': _parse_charge(gebuehr),
            'fee_centralkey': '',
            'level': '',
            'desc': ', '.join(p for p in [props.get('typ') or '', props.get('kategorie') or ''] if p),
            'type': 'toilets',
            'source': 'opendata',
        })
    return results


def fetch_luzern():
    """Stadt Luzern, Datensatz 'WC Anlagen (Toiletten)'."""
    url = ('https://map.stadtluzern.ch/server/services/OGD/toilette/MapServer/WFSServer'
           '?service=WFS&version=2.0.0&request=GetFeature&typeNames=esri:Toilette&outputFormat=GEOJSON')
    data = json.loads(_get(url))

    results = []
    for feat in data.get('features', []):
        props = feat.get('properties', {})
        if props.get('EUROKEY') != 1:
            continue
        if props.get('IN_BETRIEB') != 1:
            continue
        coords = (feat.get('geometry') or {}).get('coordinates')
        if not coords:
            continue
        lon, lat = coords[0], coords[1]

        plz = props.get('PLZ') or ''
        address = f"{plz} Luzern".strip() if plz else ''

        results.append({
            'id': f"lu_wc_{props.get('OBJECTID')}",
            'osm_id': None,
            'osm_type': '',
            'lat': lat,
            'lon': lon,
            'name': props.get('NAME') or 'Eurokey WC',
            'operator': 'Stadt Luzern',
            'address': address,
            'opening_hours': '',
            'fee': '',
            'charge': '',
            'fee_centralkey': '',
            'level': '',
            'desc': props.get('ART_TEXT') or '',
            'type': 'toilets',
            'source': 'opendata',
        })
    return results


SOURCES = [
    ('Zürich', fetch_zurich),
    ('Genf', fetch_geneva),
    ('Basel-Stadt', fetch_basel),
    ('Luzern', fetch_luzern),
]


def fetch_all(log=print):
    """Ruft alle Quellen ab; Fehler einzelner Quellen brechen den Rest nicht ab."""
    all_items = []
    for city_name, fn in SOURCES:
        try:
            items = fn()
            log(f"Open-Data {city_name}: {len(items)} Eurokey-Standorte")
            all_items.extend(items)
        except Exception as e:
            log(f"Open-Data {city_name}: Fehler - {e}")
    return all_items
