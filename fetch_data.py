import json
import urllib.request
import urllib.parse
import time
import sys

SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter"
]

BBOXES = [
    ("45.81,5.95,47.81,8.23"),
    ("45.81,8.23,47.81,10.50")
]

headers = {'User-Agent': 'EurokeyFinderCH-Bot/1.0 (GitHubActions; contact: info@series3c.ch)'}

def fetch_bbox(bbox):
    query = f"""[out:json][timeout:60];
(
  node["centralkey"="eurokey"]({bbox});
  way["centralkey"="eurokey"]({bbox});
  node["toilets:centralkey"="eurokey"]({bbox});
  way["toilets:centralkey"="eurokey"]({bbox});
  node["eurokey"="yes"]({bbox});
  way["eurokey"="yes"]({bbox});
  node["wheelchair:eurokey"="yes"]({bbox});
  way["wheelchair:eurokey"="yes"]({bbox});
);
out center;"""
    
    data = urllib.parse.urlencode({'data': query}).encode('utf-8')
    
    for server in SERVERS:
        try:
            print(f"Abfrage ({bbox}) an {server}...")
            req = urllib.request.Request(server, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=90) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                elements = result.get('elements', [])
                print(f"Erfolg: {len(elements)} Elemente von {server}.")
                return elements
        except Exception as e:
            print(f"Warnung: {server} fehlgeschlagen: {e}")
            time.sleep(2)
            
    raise RuntimeError(f"Alle Overpass-Server für BBox {bbox} fehlgeschlagen.")

def reverse_geocode_swisstopo(lat, lon):
    """Ermittelt Adresse über die offizielle Schweizer Bundes-Geodaten-API"""
    try:
        url = f"https://api3.geo.admin.ch/rest/services/api/MapServer/identify?geometryType=esriGeometryPoint&geometry={lon},{lat}&imageDisplay=100,100,100&mapExtent={lon-0.01},{lat-0.01},{lon+0.01},{lat+0.01}&tolerance=50&layers=all:ch.bfs.gebaeude_wohnungs_register&returnGeometry=false"
        req = urllib.request.Request(url, headers={'User-Agent': 'EurokeyFinderCH-Bot/1.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            results = data.get('results', [])
            if results:
                props = results[0].get('attributes', {})
                street = props.get('strname', '')
                deinr = props.get('deinr', '')
                plz = props.get('dplz4', '')
                ort = props.get('dplzname', '')
                
                parts = []
                if street:
                    parts.append(f"{street} {deinr}".strip())
                if plz or ort:
                    parts.append(f"{plz} {ort}".strip())
                return ", ".join(parts)
    except Exception:
        pass
    return ""

try:
    all_elements = []
    for i, bbox in enumerate(BBOXES):
        if i > 0:
            time.sleep(3)
        all_elements.extend(fetch_bbox(bbox))

    seen_ids = set()
    cleaned_data = []

    print("Verarbeite Standorte und ermittle Adressen...")
    for el in all_elements:
        el_id = el.get('id')
        if el_id in seen_ids:
            continue
        seen_ids.add(el_id)

        lat = el.get('lat') or (el.get('center', {}).get('lat'))
        lon = el.get('lon') or (el.get('center', {}).get('lon'))
        if not lat or not lon:
            continue

        tags = el.get('tags', {})

        name = tags.get('name') or ('Eurokey WC' if tags.get('amenity') == 'toilets' else 'Eurokey-Anlage')
        operator = tags.get('operator') or ''
        
        # OSM-Adresse prüfen
        street = tags.get('addr:street', '')
        housenumber = tags.get('addr:housenumber', '')
        postcode = tags.get('addr:postcode', '')
        city = tags.get('addr:city', '')
        
        address_parts = []
        if street:
            address_parts.append(f"{street} {housenumber}".strip())
        if postcode or city:
            address_parts.append(f"{postcode} {city}".strip())
        address = ", ".join(address_parts)

        # Wenn OSM keine Adresse hat: Reverse Geocoding via swisstopo
        if not address:
            address = reverse_geocode_swisstopo(lat, lon)
            time.sleep(0.05)  # Kurze Schonfrist für die API

        opening_hours = tags.get('opening_hours') or ''
        fee = tags.get('fee') or tags.get('charge') or ''
        level = tags.get('level') or ''
        wheelchair = tags.get('wheelchair') or ''
        typ = tags.get('amenity') or tags.get('highway') or 'Anlage'
        desc = tags.get('description') or ''

        cleaned_data.append({
            'id': f"osm_{el_id}",
            'lat': lat,
            'lon': lon,
            'name': name,
            'operator': operator,
            'address': address,
            'opening_hours': opening_hours,
            'fee': fee,
            'level': level,
            'wheelchair': wheelchair,
            'desc': desc,
            'type': typ
        })

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)

    print(f"Fertig: {len(cleaned_data)} Einträge in data.json gespeichert.")

except Exception as e:
    print(f"Kritischer Fehler: {e}")
    sys.exit(1)
