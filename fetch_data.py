import json
import urllib.request
import urllib.parse
import sys

# Bounding Box Schweiz: Süd, West, Nord, Ost
query = """
[out:json][timeout:60];
(
  node["eurokey"="yes"](45.81,5.95,47.81,10.50);
  way["eurokey"="yes"](45.81,5.95,47.81,10.50);
);
out center;
"""

url = "https://overpass-api.de/api/interpreter"
data = urllib.parse.urlencode({'data': query}).encode('utf-8')
headers = {'User-Agent': 'EurokeyMapBot/1.0 (GitHubAction; Contact: series3c)'}

req = urllib.request.Request(url, data=data, headers=headers)

try:
    print("Starte Abfrage an Overpass API...")
    with urllib.request.urlopen(req, timeout=90) as response:
        raw_data = json.loads(response.read().decode('utf-8'))
        
    elements = raw_data.get('elements', [])
    print(f"{len(elements)} Rohdaten-Elemente empfangen.")

    cleaned_data = []
    for el in elements:
        lat = el.get('lat') or (el.get('center', {}).get('lat'))
        lon = el.get('lon') or (el.get('center', {}).get('lon'))
        if not lat or not lon:
            continue
            
        tags = el.get('tags', {})
        name = tags.get('name') or ('Eurokey WC' if tags.get('amenity') == 'toilets' else 'Eurokey-Anlage')
        desc = tags.get('description') or tags.get('operator') or ''
        typ = tags.get('amenity') or tags.get('highway') or 'Anlage'

        cleaned_data.append({
            'id': el.get('id'),
            'lat': lat,
            'lon': lon,
            'name': name,
            'desc': desc,
            'type': typ
        })

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)

    print(f"Erfolgreich {len(cleaned_data)} Standorte in data.json gespeichert.")

except Exception as e:
    print(f"Fehler beim Abrufen der Daten: {e}")
    sys.exit(1)
