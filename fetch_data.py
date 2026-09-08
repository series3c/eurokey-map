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

# Schweiz in 2 Bounding-Boxes aufgeteilt: West & Ost (senkt Rechenlast drastisch)
BBOXES = [
    ("45.81,5.95,47.81,8.23"),   # Westschweiz
    ("45.81,8.23,47.81,10.50")   # Ostschweiz
]

headers = {'User-Agent': 'EurokeyFinderCH-Bot/1.0 (GitHubActions)'}

def fetch_bbox(bbox):
    query = f"""
    [out:json][timeout:60];
    (
      // 1. Offizieller Standard-Tag
      node["centralkey"="eurokey"]({bbox});
      way["centralkey"="eurokey"]({bbox});
      
      // 2. Spezifischer Toiletten-Tag
      node["toilets:centralkey"="eurokey"]({bbox});
      way["toilets:centralkey"="eurokey"]({bbox});

      // 3. Alternative und barrierefreie Tags
      node["eurokey"="yes"]({bbox});
      way["eurokey"="yes"]({bbox});
      node["wheelchair:eurokey"="yes"]({bbox});
      way["wheelchair:eurokey"="yes"]({bbox});
    );
    out center;
    """
    data = urllib.parse.urlencode({'data': query}).encode('utf-8')
    
    for server in SERVERS:
        try:
            print(f"Versuche Abfrage ({bbox}) an {server}...")
            req = urllib.request.Request(server, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=90) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                elements = result.get('elements', [])
                print(f"Erfolg: {len(elements)} Elemente von {server} erhalten.")
                return elements
        except Exception as e:
            print(f"Warnung: {server} fehlgeschlagen: {e}")
            time.sleep(2)
            
    raise RuntimeError(f"Alle Overpass-Server für BBox {bbox} fehlgeschlagen.")

try:
    all_elements = []
    for i, bbox in enumerate(BBOXES):
        if i > 0:
            time.sleep(3)  # Kurze Pause zwischen den Abfragen
        elements = fetch_bbox(bbox)
        all_elements.extend(elements)

    seen_ids = set()
    cleaned_data = []

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
        desc = tags.get('description') or tags.get('operator') or ''
        typ = tags.get('amenity') or tags.get('highway') or 'Anlage'

        cleaned_data.append({
            'id': el_id,
            'lat': lat,
            'lon': lon,
            'name': name,
            'desc': desc,
            'type': typ
        })

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)

    print(f"Fertig: {len(cleaned_data)} eindeutige Standorte in data.json gespeichert.")

except Exception as e:
    print(f"Kritischer Fehler: {e}")
    sys.exit(1)
