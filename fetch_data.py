import json
import urllib.request
import urllib.parse
import time
import os
import sys
import math

import opendata_sources

SERVERS = [
    "https://overpass.osm.ch/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter"
]

BBOXES = [
    # Schweiz (West/Ost)
    ("45.81,5.95,47.81,8.23"),
    ("45.81,8.23,47.81,10.50"),
    # Deutschland (2 Zeilen x 3 Spalten)
    ("47.27,5.87,51.15,8.95"),
    ("47.27,8.95,51.15,12.00"),
    ("47.27,12.00,51.15,15.04"),
    ("51.15,5.87,55.06,8.95"),
    ("51.15,8.95,55.06,12.00"),
    ("51.15,12.00,55.06,15.04"),
    # Österreich (West/Ost)
    ("46.37,9.53,49.02,13.35"),
    ("46.37,13.35,49.02,17.16"),
]

headers = {'User-Agent': 'EurokeyFinderDACH-Pi/1.0 (contact: info@series3c.ch)'}

def fetch_bbox(bbox):
    query = f"""[out:json][timeout:120];
(
  // Explizite Eurokey WCs & Anlagen
  node["centralkey"="eurokey"]({bbox});
  way["centralkey"="eurokey"]({bbox});
  node["toilets:centralkey"="eurokey"]({bbox});
  way["toilets:centralkey"="eurokey"]({bbox});
  node["eurokey"="yes"]({bbox});
  way["eurokey"="yes"]({bbox});
  node["toilets:eurokey"="yes"]({bbox});
  way["toilets:eurokey"="yes"]({bbox});
  node["wheelchair:eurokey"="yes"]({bbox});
  way["wheelchair:eurokey"="yes"]({bbox});

  // Barrierefreie Lifte & Hebebühnen (nur mit erkennbarem Eurokey-Bezug)
  node["highway"="elevator"]["centralkey"="eurokey"]({bbox});
  way["highway"="elevator"]["centralkey"="eurokey"]({bbox});
  node["highway"="elevator"]["wheelchair:eurokey"="yes"]({bbox});
  way["highway"="elevator"]["wheelchair:eurokey"="yes"]({bbox});
  node["wheelchair"="platform_lift"]["centralkey"="eurokey"]({bbox});
  way["wheelchair"="platform_lift"]["centralkey"="eurokey"]({bbox});
  node["wheelchair"="platform_lift"]["wheelchair:eurokey"="yes"]({bbox});
  way["wheelchair"="platform_lift"]["wheelchair:eurokey"="yes"]({bbox});
);
out center;"""
    
    data = urllib.parse.urlencode({'data': query}).encode('utf-8')
    for server in SERVERS:
        try:
            print(f"Abfrage an {server}...")
            req = urllib.request.Request(server, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=150) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                elements = result.get('elements', [])
                print(f"Erfolg: {len(elements)} Elemente empfangen.")
                return elements
        except Exception as e:
            print(f"Server-Fehler {server}: {e}")
            time.sleep(2)
            
    raise RuntimeError("Alle Overpass-Server fehlgeschlagen.")

def reverse_geocode_nominatim(lat, lon):
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            addr = data.get('address', {})
            
            road = addr.get('road') or addr.get('pedestrian') or addr.get('path') or ''
            house_nr = addr.get('house_number', '')
            postcode = addr.get('postcode', '')
            city = addr.get('city') or addr.get('town') or addr.get('village') or addr.get('municipality') or ''

            street_part = f"{road} {house_nr}".strip()
            city_part = f"{postcode} {city}".strip()

            parts = [p for p in [street_part, city_part] if p]
            return ", ".join(parts)
    except Exception:
        pass
    return ""

def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def merge_opendata(existing_items, log=print):
    """Ergaenzt amtliche Open-Data-Standorte, die nicht schon (naeherungsweise)
    an derselben Stelle aus OSM vorhanden sind."""
    opendata_items = opendata_sources.fetch_all(log=log)
    added = []
    for item in opendata_items:
        is_duplicate = any(
            haversine_m(item['lat'], item['lon'], existing['lat'], existing['lon']) < 30
            for existing in existing_items
        )
        if not is_duplicate:
            added.append(item)
    log(f"Open-Data gesamt: {len(opendata_items)} Standorte, davon {len(added)} neu (kein OSM-Duplikat < 30m).")
    return added


def determine_type_and_name(tags):
    highway = tags.get('highway', '')
    amenity = tags.get('amenity', '')
    wheelchair = tags.get('wheelchair', '')
    name = tags.get('name', '')

    if highway == 'elevator' or tags.get('elevator') == 'yes':
        poi_type = 'elevator'
        poi_name = name or 'Barrierefreier Lift'
    elif wheelchair == 'platform_lift':
        poi_type = 'platform_lift'
        poi_name = name or 'Hebebühne / Treppenlift'
    else:
        poi_type = 'toilets'
        poi_name = name or 'Eurokey WC'

    return poi_type, poi_name

try:
    # 1. Adress-Cache laden
    address_cache = {}
    if os.path.exists('data.json'):
        try:
            with open('data.json', 'r', encoding='utf-8') as f:
                old_items = json.load(f)
                for item in old_items:
                    if item.get('id') and item.get('address'):
                        address_cache[item['id']] = item['address']
            print(f"Cache geladen: {len(address_cache)} Adressen bereit.")
        except Exception:
            pass

    # 2. OSM-Daten abrufen
    all_elements = []
    for i, bbox in enumerate(BBOXES):
        if i > 0:
            time.sleep(2)
        all_elements.extend(fetch_bbox(bbox))

    seen_ids = set()
    cleaned_data = []
    
    # Vorfiltern auf eindeutige Elemente mit Koordinaten
    valid_elements = []
    for el in all_elements:
        el_id = el.get('id')
        if el_id in seen_ids:
            continue
        lat = el.get('lat') or (el.get('center', {}).get('lat'))
        lon = el.get('lon') or (el.get('center', {}).get('lon'))
        if lat and lon:
            seen_ids.add(el_id)
            valid_elements.append(el)

    total_count = len(valid_elements)
    print(f"Starte Verarbeitung von {total_count} Standorten...")

    start_time = time.time()
    new_nominatim_lookups = 0

    for idx, el in enumerate(valid_elements, start=1):
        if idx % 10 == 0 or idx == total_count:
            pct = int((idx / total_count) * 100)
            print(f"PROGRESS:{pct}:{idx}:{total_count}", flush=True)
        el_id = el.get('id')
        item_id = f"osm_{el_id}"
        lat = el.get('lat') or (el.get('center', {}).get('lat'))
        lon = el.get('lon') or (el.get('center', {}).get('lon'))

        tags = el.get('tags', {})
        poi_type, poi_name = determine_type_and_name(tags)
        operator = tags.get('operator') or ''
        
        street = tags.get('addr:street', '')
        housenumber = tags.get('addr:housenumber', '')
        postcode = tags.get('addr:postcode', '')
        city = tags.get('addr:city', '')
        
        parts = []
        if street:
            parts.append(f"{street} {housenumber}".strip())
        if postcode or city:
            parts.append(f"{postcode} {city}".strip())
        address = ", ".join(parts)

        # Cache prüfen oder via Nominatim auflösen
        if not address:
            if item_id in address_cache:
                address = address_cache[item_id]
            else:
                address = reverse_geocode_nominatim(lat, lon)
                if address:
                    address_cache[item_id] = address
                new_nominatim_lookups += 1
                time.sleep(1.05)

        cleaned_data.append({
            'id': item_id,
            'osm_id': el_id,
            'osm_type': el.get('type', 'node'),
            'lat': lat,
            'lon': lon,
            'name': poi_name,
            'operator': operator,
            'address': address,
            'opening_hours': tags.get('opening_hours', ''),
            'fee': tags.get('fee', '') or tags.get('charge', ''),
            'charge': tags.get('charge', ''),
            'fee_centralkey': tags.get('fee:centralkey', ''),
            'level': tags.get('level', ''),
            'desc': tags.get('description', ''),
            'type': poi_type
        })

        # Fortschrittsbalken aktualisieren
        elapsed = time.time() - start_time
        suffix_text = f"({idx}/{total_count}) [Neu: {new_nominatim_lookups}]"

    # 3. Amtliche Open-Data-Quellen ergaenzen (Zuerich, Genf, Basel-Stadt, Luzern)
    print("Rufe amtliche Open-Data-Quellen ab...")
    cleaned_data.extend(merge_opendata(cleaned_data))

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)

    print(f"Erfolgreich beendet: {len(cleaned_data)} Standorte gespeichert.")

except KeyboardInterrupt:
    print("\nAbgebrochen durch Benutzer. Bisherige Daten nicht überschrieben.")
    sys.exit(0)
except Exception as e:
    print(f"\nFehler: {e}")
    sys.exit(1)
