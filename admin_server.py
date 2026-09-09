import os
from flask import jsonify, request
import subprocess
import time
from flask import Flask, Response, render_template_string, jsonify, send_from_directory

app = Flask(__name__)
WORKDIR = "/home/pi/eurokey-map"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <title>Eurokey Admin & Log</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
      background: #1e1e1e;
      color: #ddd;
      margin: 0;
      padding: 16px;
    }
    .container {
      max-width: 900px;
      margin: 0 auto;
    }
    h1 {
      font-size: 20px;
      margin-bottom: 12px;
      color: #fff;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .status-badge {
      font-size: 13px;
      padding: 4px 10px;
      border-radius: 4px;
      font-weight: bold;
    }
    .active { background: #2e7d32; color: #fff; }
    .inactive { background: #555; color: #ccc; }
    .controls {
      display: flex;
      gap: 10px;
      margin-bottom: 14px;
    }
    button {
      padding: 8px 16px;
      border: none;
      border-radius: 4px;
      font-weight: bold;
      cursor: pointer;
      font-size: 13px;
    }
    .btn-start { background: #007acc; color: white; }
    .btn-stop { background: #d32f2f; color: white; }
    .btn-clear { background: #444; color: white; }
    button:disabled { opacity: 0.5; cursor: not-allowed; }

    .progress-container {
      background: #2a2a2a;
      border: 1px solid #444;
      border-radius: 6px;
      height: 24px;
      margin-bottom: 14px;
      position: relative;
      overflow: hidden;
    }
    .progress-bar {
      background: #007acc;
      height: 100%;
      width: 0%;
      transition: width 0.3s ease;
    }
    .progress-label {
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
      font-weight: bold;
      color: #fff;
      text-shadow: 0 1px 2px rgba(0,0,0,0.8);
    }

    #logBox {
      background: #000;
      color: #00ff66;
      border: 1px solid #333;
      border-radius: 6px;
      height: 55vh;
      overflow-y: auto;
      padding: 12px;
      font-size: 12px;
      white-space: pre-wrap;
      word-break: break-all;
    }
    .nav-links {
      margin-top: 12px;
      font-size: 13px;
    }
    .nav-links a {
      color: #4da3ff;
      text-decoration: none;
    }
  </style>
</head>
<body>
<div class="container">
  <h1>
    Eurokey Datenabruf Job-Steuerung
    <span id="statusBadge" class="status-badge inactive">Prüfe Status...</span>
  </h1>

  <div class="controls">
    <button id="startBtn" class="btn-start" onclick="triggerJob('start')">▶ Job jetzt starten</button>
    <button id="stopBtn" class="btn-stop" onclick="triggerJob('stop')">⏹ Job abbrechen</button>
    <button class="btn-clear" onclick="clearLog()">Log leeren</button>
  </div>

  <div class="progress-container">
    <div id="progressBar" class="progress-bar"></div>
    <div id="progressLabel" class="progress-label">Bereit</div>
  </div>

  <div id="logBox">Lade Logs...</div>

  <div class="nav-links">
    <a href="/" target="_blank">Zur Karte ↗</a>
  </div>
</div>

  <!-- Neue Standort-Vorschlaege -->
  <div style="margin-top: 35px;">
    <h2 style="font-size: 1.25rem; font-weight: 600; margin-bottom: 12px; color: #fff;">Neue Standort-Vorschläge</h2>
    <div style="background: #1e1e1e; border: 1px solid #333; border-radius: 8px; overflow-x: auto;">
      <table style="width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; color: #ccc;">
        <thead>
          <tr style="background: #252525; border-bottom: 1px solid #333; color: #aaa;">
            <th style="padding: 10px;">ID</th>
            <th style="padding: 10px;">Name</th>
            <th style="padding: 10px;">Typ</th>
            <th style="padding: 10px;">Adresse</th>
            <th style="padding: 10px;">Koordinaten</th>
            <th style="padding: 10px;">Status</th>
            <th style="padding: 10px;">Erstellt am</th>
            <th style="padding: 10px;">Aktion</th>
          </tr>
        </thead>
        <tbody id="submissionsTableBody">
          <tr><td colspan="8" style="padding: 12px; text-align: center; color: #777;">Lade Vorschläge...</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- Meldungen Tabelle -->
  <div style="margin-top: 35px;">
    <h2 style="font-size: 1.25rem; font-weight: 600; margin-bottom: 12px; color: #fff;">Aktive Community-Meldungen</h2>
    <div style="background: #1e1e1e; border: 1px solid #333; border-radius: 8px; overflow-x: auto;">
      <table style="width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; color: #ccc;">
        <thead>
          <tr style="background: #252525; border-bottom: 1px solid #333; color: #aaa; user-select: none;">
            <th onclick="sortTable('id')" style="padding: 10px; cursor: pointer;">ID <span id="sort_id">▼</span></th>
            <th onclick="sortTable('poi_id')" style="padding: 10px; cursor: pointer;">POI-ID <span id="sort_poi_id" style="color: #666;">⇅</span></th>
            <th onclick="sortTable('issue_type')" style="padding: 10px; cursor: pointer;">Status <span id="sort_issue_type" style="color: #666;">⇅</span></th>
            <th onclick="sortTable('created_at')" style="padding: 10px; cursor: pointer;">Erstellt am <span id="sort_created_at" style="color: #666;">⇅</span></th>
            <th onclick="sortTable('expires_at')" style="padding: 10px; cursor: pointer;">Gültig bis <span id="sort_expires_at" style="color: #666;">⇅</span></th>
            <th onclick="sortTable('client_ip')" style="padding: 10px; cursor: pointer;">IP <span id="sort_client_ip" style="color: #666;">⇅</span></th>
            <th style="padding: 10px;">Aktion</th>
          </tr>
        </thead>
        <tbody id="reportsTableBody">
          <tr><td colspan="7" style="padding: 12px; text-align: center; color: #777;">Lade Meldungen...</td></tr>
        </tbody>
      </table>
    </div>
  </div>

<script>
  const logBox = document.getElementById('logBox');
  const badge = document.getElementById('statusBadge');
  const startBtn = document.getElementById('startBtn');
  const stopBtn = document.getElementById('stopBtn');
  const progressBar = document.getElementById('progressBar');
  const progressLabel = document.getElementById('progressLabel');

  function clearLog() {
    logBox.innerText = '';
  }

  function setProgress(pct, text) {
    progressBar.style.width = pct + '%';
    progressLabel.innerText = text;
    if (pct > 0 && pct < 100) {
      document.title = "[" + pct + "%] Eurokey Admin";
    } else {
      document.title = "Eurokey Admin";
    }
  }

  function fetchLogs() {
    fetch('/admin/logs-poll')
      .then(r => r.json())
      .then(d => {
        if (d.logs) {
          logBox.innerText = d.logs;
          logBox.scrollTop = logBox.scrollHeight;

          // Fortschritt aus den Zeilen auslesen
          const lines = d.logs.split('\\n');
          for (let i = lines.length - 1; i >= 0; i--) {
            if (lines[i].includes('PROGRESS:')) {
              const parts = lines[i].split('PROGRESS:')[1].trim().split(':');
              if (parts.length >= 3) {
                setProgress(parts[0], `${parts[0]}% (${parts[1]}/${parts[2]} POIs verarbeitet)`);
                break;
              }
            } else if (lines[i].includes('Erfolgreich beendet:')) {
              setProgress(100, 'Fertiggestellt (100%)');
              break;
            }
          }
        }
      })
      .catch(err => console.error('Log fetch error:', err));
  }

  function updateStatus() {
    fetch('/admin/status')
      .then(r => r.json())
      .then(d => {
        if (d.running) {
          badge.className = 'status-badge active';
          badge.innerText = 'Läuft gerade...';
          startBtn.disabled = true;
          stopBtn.disabled = false;
        } else {
          badge.className = 'status-badge inactive';
          badge.innerText = 'Inaktiv';
          startBtn.disabled = false;
          stopBtn.disabled = true;
          if (progressLabel.innerText === 'Starte Abruf...') {
            progressLabel.innerText = 'Bereit';
            progressBar.style.width = '0%';
          }
        }
      });
  }

  function triggerJob(action) {
    if (action === 'start') {
      setProgress(0, 'Starte Abruf...');
    }
    fetch('/admin/' + action, { method: 'POST' })
      .then(r => r.json())
      .then(d => {
        updateStatus();
        setTimeout(fetchLogs, 500);
      });
  }

  // Initial ausführen und regelmässig abfragen
  updateStatus();
  fetchLogs();
  setInterval(updateStatus, 3000);
  setInterval(fetchLogs, 2500);

  let currentReportsData = [];
  let sortColumn = 'id';
  let sortDirection = 'desc';

  function sortTable(column) {
    if (sortColumn === column) {
      sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      sortColumn = column;
      sortDirection = 'asc';
    }
    renderReportsTable();
  }

  function renderReportsTable() {
    const tbody = document.getElementById('reportsTableBody');
    if (!currentReportsData || currentReportsData.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="padding: 10px; text-align: center; color: #888;">Keine aktiven Meldungen vorhanden.</td></tr>';
      return;
    }

    const columns = ['id', 'poi_id', 'issue_type', 'created_at', 'expires_at', 'client_ip'];
    columns.forEach(col => {
      const el = document.getElementById('sort_' + col);
      if (el) {
        if (sortColumn === col) {
          el.innerText = sortDirection === 'asc' ? ' ▲' : ' ▼';
          el.style.color = '#fff';
        } else {
          el.innerText = ' ⇅';
          el.style.color = '#666';
        }
      }
    });

    currentReportsData.sort((a, b) => {
      let valA = a[sortColumn];
      let valB = b[sortColumn];

      if (valA === undefined || valA === null) valA = '';
      if (valB === undefined || valB === null) valB = '';

      if (typeof valA === 'number' && typeof valB === 'number') {
        return sortDirection === 'asc' ? valA - valB : valB - valA;
      }

      valA = valA.toString().toLowerCase();
      valB = valB.toString().toLowerCase();

      if (valA < valB) return sortDirection === 'asc' ? -1 : 1;
      if (valA > valB) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });

    let html = '';
    currentReportsData.forEach(r => {
      html += `<tr style="border-bottom: 1px solid #333;">
        <td style="padding: 8px;">${r.id}</td>
        <td style="padding: 8px;"><a href="/?poi=${encodeURIComponent(r.poi_id)}" target="_blank" style="color: #3b82f6; text-decoration: underline;"><code>${r.poi_id}</code> ↗</a></td>
        <td style="padding: 8px;"><strong>${r.issue_type}</strong></td>
        <td style="padding: 8px;">${r.created_at}</td>
        <td style="padding: 8px;">${r.expires_at}</td>
        <td style="padding: 8px;">${r.client_ip}</td>
        <td style="padding: 8px;">
          <button onclick="deleteReport(${r.id})" style="background: #ef4444; color: white; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 12px;">Löschen</button>
        </td>
      </tr>`;
    });
    tbody.innerHTML = html;
  }

  function loadReportsTable() {
    fetch('/admin/reports-list')
      .then(r => r.json())
      .then(rows => {
        currentReportsData = rows;
        renderReportsTable();
      });
  }
  loadReportsTable();
  setInterval(loadReportsTable, 5000);

  function deleteReport(id) {
      if (!confirm('Meldung #' + id + ' wirklich löschen?')) return;
      fetch('/admin/delete-report', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({id: id})
      })
      .then(r => r.json())
      .then(res => {
        if (res.success) loadReportsTable();
        else alert('Fehler: ' + (res.error || 'Konnte nicht gelöscht werden'));
      });
    }

    loadReportsTable();

    const typeLabelsAdmin = {
      toilets: 'WC', elevator: 'Lift', platform_lift: 'Hebebühne',
      shower: 'Dusche', changing_room: 'Umkleide', door: 'Tür/Barriere'
    };

    function renderSubmissionsTable(rows) {
      const tbody = document.getElementById('submissionsTableBody');
      if (!rows || rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="padding: 10px; text-align: center; color: #888;">Keine Vorschläge vorhanden.</td></tr>';
        return;
      }
      let html = '';
      rows.forEach(r => {
        const statusColor = r.status === 'approved' ? '#2e7d32' : (r.status === 'pending' ? '#b45309' : '#888');
        html += `<tr style="border-bottom: 1px solid #333;">
          <td style="padding: 8px;">${r.id}</td>
          <td style="padding: 8px;">${r.name || '(ohne Namen)'}</td>
          <td style="padding: 8px;">${typeLabelsAdmin[r.type] || r.type}</td>
          <td style="padding: 8px;">${r.address || '–'}</td>
          <td style="padding: 8px;"><a href="https://www.openstreetmap.org/?mlat=${r.lat}&mlon=${r.lon}#map=18/${r.lat}/${r.lon}" target="_blank" style="color:#3b82f6;">${Number(r.lat).toFixed(5)}, ${Number(r.lon).toFixed(5)} ↗</a></td>
          <td style="padding: 8px; color: ${statusColor}; font-weight: bold;">${r.status}</td>
          <td style="padding: 8px;">${r.created_at}</td>
          <td style="padding: 8px; white-space: nowrap;">
            ${r.status !== 'approved' ? `<button onclick="approveSubmission(${r.id})" style="background: #2e7d32; color: white; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 12px; margin-right: 4px;">Freigeben</button>` : ''}
            <button onclick="deleteSubmission(${r.id})" style="background: #ef4444; color: white; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 12px;">Löschen</button>
          </td>
        </tr>`;
      });
      tbody.innerHTML = html;
    }

    function loadSubmissionsTable() {
      fetch('/admin/submissions-list')
        .then(r => r.json())
        .then(rows => renderSubmissionsTable(rows));
    }

    function approveSubmission(id) {
      fetch('/admin/approve-submission', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({id: id})
      }).then(r => r.json()).then(res => {
        if (res.success) loadSubmissionsTable();
        else alert('Fehler: ' + (res.error || 'Konnte nicht freigegeben werden'));
      });
    }

    function deleteSubmission(id) {
      if (!confirm('Vorschlag #' + id + ' wirklich löschen?')) return;
      fetch('/admin/delete-submission', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({id: id})
      }).then(r => r.json()).then(res => {
        if (res.success) loadSubmissionsTable();
        else alert('Fehler: ' + (res.error || 'Konnte nicht gelöscht werden'));
      });
    }

    loadSubmissionsTable();
    setInterval(loadSubmissionsTable, 5000);
  </script>
</body>
</html>
"""

@app.route('/admin')
def admin():
    return render_template_string(HTML_TEMPLATE)

@app.route('/admin/status')
def status():
    res = subprocess.run(['systemctl', 'is-active', 'eurokey-fetch.service'], capture_output=True, text=True)
    is_running = (res.stdout.strip() in ['activating', 'active'])
    return jsonify({'running': is_running})

@app.route('/admin/start', methods=['POST'])
def start_job():
    subprocess.run(['sudo', 'systemctl', 'start', 'eurokey-fetch.service'])
    return jsonify({'status': 'started'})

@app.route('/admin/stop', methods=['POST'])
def stop_job():
    subprocess.run(['sudo', 'systemctl', 'stop', 'eurokey-fetch.service'])
    return jsonify({'status': 'stopped'})


@app.route('/admin/logs-static')
def logs_static():
    cmd = ['journalctl', '-u', 'eurokey-fetch.service', '-n', '80', '--no-pager']
    res = subprocess.run(cmd, capture_output=True, text=True)
    return jsonify({'logs': res.stdout})

@app.route('/admin/logs-poll')
def logs_poll():
    cmd = ['journalctl', '-u', 'eurokey-fetch.service', '-n', '80', '--no-pager']
    res = subprocess.run(cmd, capture_output=True, text=True)
    return jsonify({'logs': res.stdout})

@app.route('/')
def index():
    resp = send_from_directory(WORKDIR, 'index.html')
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(WORKDIR, path)


# --- Community Report API ---
import sqlite3
from datetime import datetime, timedelta

DB_PATH = os.path.join(WORKDIR, "reports.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_submissions_table():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            name TEXT,
            type TEXT NOT NULL,
            address TEXT,
            opening_hours TEXT,
            fee TEXT,
            desc TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            client_ip TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

ensure_submissions_table()

VALID_SUBMISSION_TYPES = ["toilets", "elevator", "platform_lift", "shower", "changing_room", "door"]

@app.route("/api/reports", methods=["GET"])
def get_reports():
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT poi_id, issue_type, COUNT(*) as count 
        FROM reports 
        WHERE expires_at > ? 
        GROUP BY poi_id, issue_type
    """, (now,))
    rows = c.fetchall()
    conn.close()

    result = {}
    for r in rows:
        pid = r["poi_id"]
        if pid not in result:
            result[pid] = {}
        result[pid][r["issue_type"]] = r["count"]

    return jsonify(result)

@app.route("/api/report", methods=["POST"])
def post_report():
    data = request.get_json() or {}
    
    # Honeypot-Pruefung
    if data.get("website"):
        return jsonify({"status": "ignored"}), 200

    poi_id = data.get("poi_id")
    issue_type = data.get("issue_type")

    valid_types = ["dirty", "broken", "inaccessible", "ok"]
    if not poi_id or issue_type not in valid_types:
        return jsonify({"error": "Ungueltige Daten"}), 400

    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr).split(",")[0].strip()
    now_dt = datetime.utcnow()
    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    c = conn.cursor()

    # Wenn "ok" gemeldet wird, alle aktiven Stoerungen fuer dieses POI direkt ablaufen lassen
    if issue_type == "ok":
        c.execute("UPDATE reports SET expires_at = ? WHERE poi_id = ? AND expires_at > ?", (now_str, poi_id, now_str))
        conn.commit()
        conn.close()
        return jsonify({"status": "resolved"}), 200

    # Rate-Limit: Max. 1 Meldung pro POI und IP innerhalb 24h
    one_day_ago = (now_dt - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("SELECT id FROM reports WHERE poi_id = ? AND client_ip = ? AND created_at > ?", (poi_id, client_ip, one_day_ago))
    if c.fetchone():
        conn.close()
        return jsonify({"error": "Du hast diesen Standort heute bereits bewertet."}), 429

    # TTL-Berechnung
    ttl_hours = 48 if issue_type == "dirty" else (7 * 24)
    expires_dt = now_dt + timedelta(hours=ttl_hours)
    expires_str = expires_dt.strftime("%Y-%m-%d %H:%M:%S")

    c.execute("""
        INSERT INTO reports (poi_id, issue_type, created_at, expires_at, client_ip)
        VALUES (?, ?, ?, ?, ?)
    """, (poi_id, issue_type, now_str, expires_str, client_ip))

    conn.commit()
    conn.close()
    return jsonify({"status": "success"}), 201

@app.route("/api/submit-location", methods=["POST"])
def submit_location():
    data = request.get_json() or {}

    # Honeypot-Pruefung
    if data.get("website"):
        return jsonify({"status": "ignored"}), 200

    try:
        lat = float(data.get("lat"))
        lon = float(data.get("lon"))
    except (TypeError, ValueError):
        return jsonify({"error": "Ungueltige Koordinaten"}), 400

    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return jsonify({"error": "Ungueltige Koordinaten"}), 400

    poi_type = data.get("type")
    if poi_type not in VALID_SUBMISSION_TYPES:
        return jsonify({"error": "Ungueltiger Typ"}), 400

    name = (data.get("name") or "").strip()[:200]
    address = (data.get("address") or "").strip()[:300]
    opening_hours = (data.get("opening_hours") or "").strip()[:200]
    fee = (data.get("fee") or "").strip()[:100]
    desc = (data.get("desc") or "").strip()[:500]

    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr).split(",")[0].strip()
    now_dt = datetime.utcnow()
    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    c = conn.cursor()

    # Rate-Limit: max. 5 Vorschlaege pro IP innerhalb 24h
    one_day_ago = (now_dt - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("SELECT COUNT(*) FROM submissions WHERE client_ip = ? AND created_at > ?", (client_ip, one_day_ago))
    if c.fetchone()[0] >= 5:
        conn.close()
        return jsonify({"error": "Zu viele Vorschlaege heute. Bitte versuch es morgen wieder."}), 429

    c.execute("""
        INSERT INTO submissions (lat, lon, name, type, address, opening_hours, fee, desc, status, created_at, client_ip)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
    """, (lat, lon, name, poi_type, address, opening_hours, fee, desc, now_str, client_ip))

    conn.commit()
    conn.close()
    return jsonify({"status": "success"}), 201

@app.route("/api/community-locations", methods=["GET"])
def get_community_locations():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT id, lat, lon, name, type, address, opening_hours, fee, desc
        FROM submissions WHERE status = 'approved'
    """)
    rows = c.fetchall()
    conn.close()

    result = []
    for r in rows:
        result.append({
            'id': f"community_{r['id']}",
            'lat': r['lat'],
            'lon': r['lon'],
            'name': r['name'] or 'Community-Standort',
            'operator': 'Community-Meldung',
            'address': r['address'] or '',
            'opening_hours': r['opening_hours'] or '',
            'fee': r['fee'] or '',
            'level': '',
            'desc': r['desc'] or '',
            'type': r['type'],
            'source': 'community'
        })
    return jsonify(result)

@app.route('/admin/submissions-list')
def admin_submissions_list():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT id, lat, lon, name, type, address, opening_hours, fee, desc, status, created_at, client_ip
        FROM submissions
        ORDER BY id DESC
    ''')
    rows = c.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/admin/approve-submission', methods=['POST'])
def admin_approve_submission():
    data = request.get_json() or {}
    sub_id = data.get('id')
    if not sub_id:
        return jsonify({'success': False, 'error': 'Keine ID uebergeben'}), 400

    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE submissions SET status = 'approved' WHERE id = ?", (sub_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/admin/delete-submission', methods=['POST'])
def admin_delete_submission():
    data = request.get_json() or {}
    sub_id = data.get('id')
    if not sub_id:
        return jsonify({'success': False, 'error': 'Keine ID uebergeben'}), 400

    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM submissions WHERE id = ?", (sub_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/admin/reports-list')
def admin_reports_list():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT id, poi_id, issue_type, created_at, expires_at, client_ip
        FROM reports
        ORDER BY id DESC
    ''')
    rows = c.fetchall()
    conn.close()
    
    result = []
    for r in rows:
        result.append({
            'id': r['id'],
            'poi_id': r['poi_id'],
            'issue_type': r['issue_type'],
            'created_at': r['created_at'],
            'expires_at': r['expires_at'],
            'client_ip': r['client_ip']
        })
    return jsonify(result)

@app.route('/admin/delete-report', methods=['POST'])
def admin_delete_report():
    data = request.get_json() or {}
    report_id = data.get('id')
    if not report_id:
        return jsonify({'success': False, 'error': 'Keine ID uebergeben'}), 400
        
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM reports WHERE id = ?", (report_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
