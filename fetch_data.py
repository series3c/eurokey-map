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

headers = {'User-Agent': 'EurokeyFinderCH-Bot/1.0 (GitHubActions)'}

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
            time.sleep(3)
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

        # Name & Betreiber
        name = tags.get('name') or ('Eurokey WC' if tags.get('amenity') == 'toilets' else 'Eurokey-Anlage')
        operator = tags.get('operator') or ''
        
        # Adresse zusammenbauen
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

        # Zusätzliche Details
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

    print(f"Fertig: {len(cleaned_data)} Einträge mit Detail-Tags gespeichert.")

except Exception as e:
    print(f"Kritischer Fehler: {e}")
    sys.exit(1)
