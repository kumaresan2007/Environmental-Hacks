"""
NeerWatch Administration & Cadastral Workspace Server
Python standard-library HTTP server & REST API with SQLite backend.
"""

import http.server
import socketserver
import json
import sqlite3
import os
import mimetypes
import urllib.parse
import hashlib
import secrets
from datetime import datetime, timedelta
import csv
import io

from database import (
    get_db_connection,
    verify_password,
    hash_password,
    needs_hash_upgrade,
    init_db,
    get_db_path
)

PORT = 8080
PUBLIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")

# Session storage: token -> {user_id, email, role, full_name, designation, created_at, expires_at}
SESSIONS = {}
SESSION_TTL_HOURS = 24

def get_current_user(headers):
    # Check Authorization header or Cookie
    auth_header = headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "X-Session-Token" in headers:
        token = headers.get("X-Session-Token").strip()
    else:
        # Check cookie
        cookie_header = headers.get("Cookie", "")
        for part in cookie_header.split(";"):
            part = part.strip()
            if part.startswith("session_token="):
                token = part.split("=")[1].strip()
                break

    if token and token in SESSIONS:
        session_data = SESSIONS[token]
        # Check expiration
        expires_at = session_data.get("expires_at")
        if expires_at and datetime.now() > expires_at:
            del SESSIONS[token]
            return None, None
        return session_data, token
    return None, None

def log_audit_event(user_id, email, event_type, status, details):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO audit_logins (user_id, email, event_type, status, timestamp, details)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, email, event_type, status, ts, details))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging audit event: {e}")

class NeerWatchRequestHandler(http.server.BaseHTTPRequestHandler):

    def get_cors_origin(self):
        origin = self.headers.get("Origin", "")
        if origin and ("localhost" in origin or "127.0.0.1" in origin):
            return origin
        return "http://127.0.0.1:8080"

    def send_json(self, status_code, data, extra_headers=None):
        response_body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_body)))
        self.send_header("Access-Control-Allow-Origin", self.get_cors_origin())
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Session-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(response_body)

    def send_error_json(self, status_code, message, error_code=None):
        self.send_json(status_code, {
            "error": message,
            "code": error_code or f"ERR_{status_code}",
            "timestamp": datetime.now().isoformat()
        })

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", self.get_cors_origin())
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Session-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/"):
            self.handle_api_get(path, urllib.parse.parse_qs(parsed.query))
            return

        self.serve_static_file(path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/"):
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else ""
            self.handle_api_post(path, body)
            return

        self.send_error_json(404, "Endpoint not found")

    def handle_api_get(self, path, query_params):
        user, _ = get_current_user(self.headers)

        # /api/auth/me
        if path == "/api/auth/me":
            if not user:
                self.send_json(200, {"authenticated": False, "user": None})
                return
            self.send_json(200, {"authenticated": True, "user": user})
            return

        # /api/dashboard (Real summary metrics and activity)
        if path == "/api/dashboard":
            conn = get_db_connection()
            cursor = conn.cursor()

            # Water bodies count and area
            cursor.execute("SELECT COUNT(*), COALESCE(SUM(area_hectares), 0.0) FROM water_bodies")
            wb_row = cursor.fetchone()
            total_waterbodies, total_area_hectares = wb_row[0], round(wb_row[1], 1)

            # Change alerts metrics
            cursor.execute("SELECT COUNT(*) FROM change_alerts WHERE status != 'Resolved'")
            active_alerts_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM change_alerts WHERE status != 'Resolved' AND severity = 'High'")
            high_severity_alerts = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM change_alerts WHERE status = 'Resolved'")
            resolved_alerts_count = cursor.fetchone()[0]

            # Areas under review (distinct water bodies with open alerts)
            cursor.execute("SELECT COUNT(DISTINCT record_id) FROM change_alerts WHERE status != 'Resolved'")
            areas_under_review = cursor.fetchone()[0]

            # Zone breakdown
            cursor.execute("""
                SELECT zone, COUNT(*) as count, COALESCE(SUM(area_hectares), 0.0) as total_area
                FROM water_bodies
                GROUP BY zone
                ORDER BY total_area DESC
            """)
            zone_distribution = []
            for r in cursor.fetchall():
                zone_distribution.append({
                    "zone": r["zone"],
                    "count": r["count"],
                    "total_area": round(r["total_area"], 1)
                })

            # Detect current active cycle from alerts
            cursor.execute("SELECT cycle FROM change_alerts ORDER BY id DESC LIMIT 1")
            cycle_row = cursor.fetchone()
            active_cycle = cycle_row["cycle"] if cycle_row else "2026-Q3"

            # Recent activity combining audits and alert reviews
            cursor.execute("""
                SELECT 'AUDIT' as type, timestamp, email as actor, event_type as title, details, status
                FROM audit_logins
                UNION ALL
                SELECT 'REVIEW' as type, reviewed_at as timestamp, reviewer_email as actor, 
                       'Alert ' || alert_id || ' -> ' || new_status as title, notes as details, 'SUCCESS' as status
                FROM alert_reviews
                ORDER BY timestamp DESC
                LIMIT 10
            """)
            recent_activity = []
            for r in cursor.fetchall():
                recent_activity.append({
                    "type": r["type"],
                    "timestamp": r["timestamp"],
                    "actor": r["actor"],
                    "title": r["title"],
                    "details": r["details"],
                    "status": r["status"]
                })

            conn.close()

            self.send_json(200, {
                "total_waterbodies": total_waterbodies,
                "total_area_hectares": total_area_hectares,
                "active_alerts_count": active_alerts_count,
                "high_severity_alerts": high_severity_alerts,
                "areas_under_review": areas_under_review,
                "resolved_alerts_count": resolved_alerts_count,
                "active_cycle": active_cycle,
                "zone_distribution": zone_distribution,
                "recent_activity": recent_activity
            })
            return

        # /api/users
        if path == "/api/users":
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT role, COUNT(*) as count FROM users GROUP BY role")
            counts_map = {"admin": 0, "reviewer": 0, "viewer": 0}
            total_users = 0
            for row in cursor.fetchall():
                r = row["role"]
                cnt = row["count"]
                counts_map[r] = cnt
                total_users += cnt

            cursor.execute("""
                SELECT id, full_name, email, role, designation, created_at 
                FROM users 
                ORDER BY id ASC
            """)
            users = []
            for row in cursor.fetchall():
                users.append({
                    "id": row["id"],
                    "full_name": row["full_name"],
                    "email": row["email"],
                    "role": row["role"],
                    "designation": row["designation"] if row["designation"] else "Not provided",
                    "created_at": row["created_at"] if row["created_at"] else "Not provided"
                })
            conn.close()

            self.send_json(200, {
                "counts": {
                    "total": total_users,
                    "admin": counts_map.get("admin", 0),
                    "reviewer": counts_map.get("reviewer", 0),
                    "viewer": counts_map.get("viewer", 0)
                },
                "users": users
            })
            return

        # /api/audit/logins
        if path == "/api/audit/logins":
            limit = int(query_params.get("limit", [20])[0])
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, user_id, email, event_type, status, timestamp, details
                FROM audit_logins
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            logs = []
            for row in cursor.fetchall():
                logs.append({
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "email": row["email"],
                    "event_type": row["event_type"],
                    "status": row["status"],
                    "timestamp": row["timestamp"],
                    "details": row["details"]
                })
            conn.close()
            self.send_json(200, {"logs": logs})
            return

        # /api/waterbodies or /api/waterbodies/<id_or_record_id>
        if path.startswith("/api/waterbodies"):
            sub_id = path[len("/api/waterbodies"):].lstrip("/")
            conn = get_db_connection()
            cursor = conn.cursor()

            if sub_id:
                # Single waterbody detail view
                cursor.execute("""
                    SELECT id, record_id, waterbody_name, zone, area_hectares, geometry, crs, status, created_at, updated_at
                    FROM water_bodies
                    WHERE record_id = ? OR id = ?
                """, (sub_id, sub_id))
                row = cursor.fetchone()
                if not row:
                    conn.close()
                    self.send_error_json(404, f"Waterbody '{sub_id}' not found.")
                    return

                try:
                    geom = json.loads(row["geometry"])
                except Exception:
                    geom = None

                # Fetch all alerts for this waterbody
                cursor.execute("""
                    SELECT id, alert_type, severity, cycle, status, detected_at, area_change_pct, details, review_notes
                    FROM change_alerts
                    WHERE record_id = ?
                    ORDER BY id DESC
                """, (row["record_id"],))
                alerts = [dict(r) for r in cursor.fetchall()]
                conn.close()

                self.send_json(200, {
                    "id": row["id"],
                    "record_id": row["record_id"],
                    "waterbody_name": row["waterbody_name"],
                    "zone": row["zone"],
                    "area_hectares": row["area_hectares"],
                    "geometry": geom,
                    "crs": row["crs"],
                    "status": row["status"] if "status" in row.keys() else "Monitored",
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "alerts": alerts
                })
                return

            # Collection with filtering
            search_query = query_params.get("search", [""])[0].strip().lower()
            zone_filter = query_params.get("zone", [""])[0].strip()
            status_filter = query_params.get("status", [""])[0].strip()

            sql = "SELECT id, record_id, waterbody_name, zone, area_hectares, geometry, crs, status, updated_at FROM water_bodies WHERE 1=1"
            params = []

            if zone_filter and zone_filter != "All":
                sql += " AND zone = ?"
                params.append(zone_filter)

            if search_query:
                sql += " AND (LOWER(waterbody_name) LIKE ? OR LOWER(record_id) LIKE ? OR LOWER(zone) LIKE ?)"
                params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])

            sql += " ORDER BY id ASC"
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()

            # Active alerts count map
            cursor.execute("""
                SELECT record_id, COUNT(*) as alert_count, MAX(severity) as max_severity
                FROM change_alerts
                WHERE status != 'Resolved'
                GROUP BY record_id
            """)
            alerts_map = {r["record_id"]: (r["alert_count"], r["max_severity"]) for r in cursor.fetchall()}
            conn.close()

            features = []
            for row in rows:
                try:
                    geom = json.loads(row["geometry"])
                except Exception:
                    geom = None

                rec_id = row["record_id"]
                alert_info = alerts_map.get(rec_id, (0, "None"))
                computed_status = "Under Review" if alert_info[0] > 0 else (row["status"] or "Monitored")

                if status_filter and status_filter != "All":
                    if status_filter == "Under Review" and alert_info[0] == 0:
                        continue
                    elif status_filter == "Monitored" and alert_info[0] > 0:
                        continue

                features.append({
                    "type": "Feature",
                    "properties": {
                        "id": row["id"],
                        "record_id": row["record_id"],
                        "waterbody_name": row["waterbody_name"],
                        "zone": row["zone"],
                        "area_hectares": row["area_hectares"],
                        "crs": row["crs"],
                        "status": computed_status,
                        "active_alerts_count": alert_info[0],
                        "max_severity": alert_info[1],
                        "updated_at": row["updated_at"]
                    },
                    "geometry": geom
                })

            geojson = {
                "type": "FeatureCollection",
                "crs": {
                    "type": "name",
                    "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}
                },
                "features": features
            }
            self.send_json(200, geojson)
            return

        # /api/alerts
        if path.startswith("/api/alerts"):
            sub_id = path[len("/api/alerts"):].lstrip("/")
            conn = get_db_connection()
            cursor = conn.cursor()

            if sub_id:
                # Single alert with review notes history
                cursor.execute("""
                    SELECT id, record_id, waterbody_name, alert_type, severity, cycle, status, detected_at, area_change_pct, details,
                           last_reviewed_by, last_reviewed_at, review_notes
                    FROM change_alerts
                    WHERE id = ? OR record_id = ?
                """, (sub_id, sub_id))
                row = cursor.fetchone()
                if not row:
                    conn.close()
                    self.send_error_json(404, f"Alert '{sub_id}' not found.")
                    return

                alert_id = row["id"]
                cursor.execute("""
                    SELECT id, reviewer_email, reviewer_name, previous_status, new_status, notes, reviewed_at
                    FROM alert_reviews
                    WHERE alert_id = ?
                    ORDER BY id DESC
                """, (alert_id,))
                reviews = [dict(r) for r in cursor.fetchall()]
                conn.close()

                alert_data = dict(row)
                alert_data["reviews_history"] = reviews
                self.send_json(200, alert_data)
                return

            # Collection with search, filter, and sorting
            search_query = query_params.get("search", [""])[0].strip().lower()
            severity_filter = query_params.get("severity", [""])[0].strip()
            status_filter = query_params.get("status", [""])[0].strip()
            zone_filter = query_params.get("zone", [""])[0].strip()
            sort_order = query_params.get("sort", ["date_desc"])[0].strip()

            sql = """
                SELECT a.id, a.record_id, a.waterbody_name, a.alert_type, a.severity, a.cycle, a.status, 
                       a.detected_at, a.area_change_pct, a.details, a.last_reviewed_by, a.last_reviewed_at, a.review_notes,
                       w.zone
                FROM change_alerts a
                LEFT JOIN water_bodies w ON a.record_id = w.record_id
                WHERE 1=1
            """
            params = []

            if severity_filter and severity_filter != "All":
                sql += " AND a.severity = ?"
                params.append(severity_filter)

            if status_filter and status_filter != "All":
                sql += " AND a.status = ?"
                params.append(status_filter)

            if zone_filter and zone_filter != "All":
                sql += " AND w.zone = ?"
                params.append(zone_filter)

            if search_query:
                sql += " AND (LOWER(a.waterbody_name) LIKE ? OR LOWER(a.record_id) LIKE ? OR LOWER(a.alert_type) LIKE ?)"
                params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])

            # Sorting
            if sort_order == "date_asc":
                sql += " ORDER BY a.detected_at ASC"
            elif sort_order == "severity_desc":
                sql += """ ORDER BY CASE a.severity 
                             WHEN 'High' THEN 1 
                             WHEN 'Medium' THEN 2 
                             WHEN 'Low' THEN 3 
                             ELSE 4 END ASC, a.detected_at DESC"""
            else:
                sql += " ORDER BY a.detected_at DESC"

            cursor.execute(sql, tuple(params))
            alerts = []
            for row in cursor.fetchall():
                alerts.append({
                    "id": row["id"],
                    "record_id": row["record_id"],
                    "waterbody_name": row["waterbody_name"],
                    "alert_type": row["alert_type"],
                    "severity": row["severity"],
                    "cycle": row["cycle"],
                    "status": row["status"],
                    "detected_at": row["detected_at"],
                    "area_change_pct": row["area_change_pct"],
                    "details": row["details"],
                    "zone": row["zone"] or "Chennai Metro Area",
                    "last_reviewed_by": row["last_reviewed_by"],
                    "last_reviewed_at": row["last_reviewed_at"],
                    "review_notes": row["review_notes"]
                })

            cursor.execute("SELECT COUNT(*) FROM change_alerts WHERE status != 'Resolved'")
            active_count = cursor.fetchone()[0]
            conn.close()

            self.send_json(200, {
                "active_count": active_count,
                "total_matched": len(alerts),
                "alerts": alerts
            })
            return

        # /api/export/waterbodies.geojson
        if path == "/api/export/waterbodies.geojson":
            zone_filter = query_params.get("zone", [""])[0].strip()
            conn = get_db_connection()
            cursor = conn.cursor()
            sql = "SELECT record_id, waterbody_name, zone, area_hectares, geometry, crs, updated_at FROM water_bodies"
            params = []
            if zone_filter and zone_filter != "All":
                sql += " WHERE zone = ?"
                params.append(zone_filter)
            cursor.execute(sql, tuple(params))
            features = []
            for row in cursor.fetchall():
                try:
                    geom = json.loads(row["geometry"])
                except Exception:
                    geom = None
                features.append({
                    "type": "Feature",
                    "properties": {
                        "record_id": row["record_id"],
                        "waterbody_name": row["waterbody_name"],
                        "zone": row["zone"],
                        "area_hectares": row["area_hectares"],
                        "crs": row["crs"],
                        "updated_at": row["updated_at"]
                    },
                    "geometry": geom
                })
            conn.close()

            data = {
                "type": "FeatureCollection",
                "workspace": "CMA Cadastral GIS - Water Resources",
                "export_date": datetime.now().isoformat(),
                "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
                "features": features
            }
            body = json.dumps(data, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/geo+json")
            self.send_header("Content-Disposition", 'attachment; filename="cma_water_bodies_cadastral.geojson"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # /api/export/waterbodies.csv
        if path == "/api/export/waterbodies.csv":
            zone_filter = query_params.get("zone", [""])[0].strip()
            conn = get_db_connection()
            cursor = conn.cursor()
            sql = "SELECT record_id, waterbody_name, zone, area_hectares, crs, updated_at FROM water_bodies"
            params = []
            if zone_filter and zone_filter != "All":
                sql += " WHERE zone = ?"
                params.append(zone_filter)
            cursor.execute(sql, tuple(params))
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["record_id", "waterbody_name", "zone", "area_hectares", "crs", "updated_at"])
            for row in cursor.fetchall():
                writer.writerow([row["record_id"], row["waterbody_name"], row["zone"], row["area_hectares"], row["crs"], row["updated_at"]])
            conn.close()
            csv_data = output.getvalue().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="cma_water_bodies.csv"')
            self.send_header("Content-Length", str(len(csv_data)))
            self.end_headers()
            self.wfile.write(csv_data)
            return

        # /api/export/alerts.csv
        if path == "/api/export/alerts.csv":
            status_filter = query_params.get("status", [""])[0].strip()
            severity_filter = query_params.get("severity", [""])[0].strip()
            conn = get_db_connection()
            cursor = conn.cursor()
            sql = "SELECT record_id, waterbody_name, alert_type, severity, cycle, status, detected_at, area_change_pct, details, review_notes FROM change_alerts WHERE 1=1"
            params = []
            if status_filter and status_filter != "All":
                sql += " AND status = ?"
                params.append(status_filter)
            if severity_filter and severity_filter != "All":
                sql += " AND severity = ?"
                params.append(severity_filter)
            cursor.execute(sql, tuple(params))
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["record_id", "waterbody_name", "alert_type", "severity", "cycle", "status", "detected_at", "area_change_pct", "details", "review_notes"])
            for row in cursor.fetchall():
                writer.writerow([
                    row["record_id"], row["waterbody_name"], row["alert_type"],
                    row["severity"], row["cycle"], row["status"],
                    row["detected_at"], row["area_change_pct"], row["details"], row["review_notes"] or ""
                ])
            conn.close()
            csv_data = output.getvalue().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="cma_change_alerts.csv"')
            self.send_header("Content-Length", str(len(csv_data)))
            self.end_headers()
            self.wfile.write(csv_data)
            return

        # /api/export/digest.pdf
        if path == "/api/export/digest.pdf":
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), SUM(area_hectares) FROM water_bodies")
            row_wb = cursor.fetchone()
            wb_count, total_area = row_wb[0], row_wb[1] or 0.0

            cursor.execute("SELECT COUNT(*) FROM change_alerts WHERE status != 'Resolved'")
            alert_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]

            cursor.execute("SELECT record_id, waterbody_name, alert_type, severity, status, detected_at FROM change_alerts ORDER BY id DESC LIMIT 10")
            alert_rows = cursor.fetchall()
            conn.close()

            rows_html = "".join([f"""<tr>
                <td>{r['record_id']}</td>
                <td>{r['waterbody_name']}</td>
                <td>{r['alert_type']}</td>
                <td><strong>{r['severity']}</strong></td>
                <td>{r['status']}</td>
                <td>{r['detected_at']}</td>
            </tr>""" for r in alert_rows])

            html_digest = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>NeerWatch CMA Executive Cadastral Digest - 2026</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; color: #0E1E1C; background: #fff; line-height: 1.4; }}
  .header {{ border-bottom: 2px solid #0D5C58; padding-bottom: 12px; margin-bottom: 24px; }}
  .title {{ font-size: 22px; font-weight: 700; color: #004340; }}
  .subtitle {{ font-size: 13px; color: #3F4947; margin-top: 4px; }}
  .metric-grid {{ display: flex; gap: 16px; margin: 20px 0; }}
  .metric-card {{ flex: 1; padding: 14px; background: #E5F8F3; border: 1px solid #BEC9C7; border-radius: 4px; }}
  .metric-label {{ font-size: 10.5px; text-transform: uppercase; color: #3F4947; letter-spacing: 0.5px; }}
  .metric-val {{ font-size: 22px; font-weight: 700; color: #0D5C58; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 12px; }}
  th, td {{ border: 1px solid #BEC9C7; padding: 7px 10px; text-align: left; }}
  th {{ background: #E5F8F3; color: #004340; font-weight: 600; }}
  .footer {{ margin-top: 36px; font-size: 11px; color: #666; border-top: 1px solid #BEC9C7; padding-top: 10px; display: flex; justify-content: space-between; }}
  @media print {{ body {{ margin: 15mm; }} }}
</style>
</head>
<body onload="window.print()">
  <div class="header">
    <div class="title">NeerWatch • Executive Spatial Cadastral Digest</div>
    <div class="subtitle">Chennai Metro Area (CMA) Water Resources Monitoring Division • Tamil Nadu Cadastral GIS</div>
    <div class="subtitle" style="margin-top:4px; font-weight:600;">Cycle: NE Monsoon 2026-Q3 | Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
  </div>

  <div class="metric-grid">
    <div class="metric-card">
      <div class="metric-label">Monitored Water Bodies</div>
      <div class="metric-val">{wb_count}</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Total Cadastral Area</div>
      <div class="metric-val">{total_area:,.1f} ha</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Active Change Alerts</div>
      <div class="metric-val">{alert_count}</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Authorized Personnel</div>
      <div class="metric-val">{user_count}</div>
    </div>
  </div>

  <h3 style="margin-top: 24px; color: #004340;">Current Cycle Change Surveillance Log</h3>
  <table>
    <thead>
      <tr>
        <th>Record ID</th>
        <th>Water Body</th>
        <th>Alert Type</th>
        <th>Severity</th>
        <th>Status</th>
        <th>Detected</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>

  <div class="footer">
    <span>Chennai Metro Area Water Resources Cadastral GIS</span>
    <span>Certified Server Datastore • Confidential Government Workspace</span>
  </div>
</body>
</html>"""
            body_bytes = html_digest.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Disposition", 'inline; filename="neerwatch_executive_digest.html"')
            self.send_header("Content-Length", str(len(body_bytes)))
            self.end_headers()
            self.wfile.write(body_bytes)
            return

        self.send_error_json(404, f"API route not found: {path}")

    def handle_api_post(self, path, body):
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self.send_error_json(400, "Invalid JSON payload")
            return

        # /api/auth/login
        if path == "/api/auth/login":
            email = (data.get("email") or "").strip().lower()
            password = data.get("password") or ""

            if not email or not password:
                self.send_error_json(400, "Email and password are required")
                return

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, full_name, email, role, designation, password_hash, salt FROM users WHERE LOWER(email) = ?", (email,))
            user_row = cursor.fetchone()

            if not user_row or not verify_password(password, user_row["salt"], user_row["password_hash"]):
                conn.close()
                log_audit_event(
                    user_id=user_row["id"] if user_row else None,
                    email=email,
                    event_type="FAILED_AUTH",
                    status="FAILED",
                    details="Invalid credentials provided during sign-in attempt"
                )
                self.send_error_json(401, "Invalid email or password", "ERR_INVALID_CREDENTIALS")
                return

            # Check if password hash needs upgrade to PBKDF2
            if needs_hash_upgrade(user_row["password_hash"]):
                new_hash, new_salt = hash_password(password)
                cursor.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?", (new_hash, new_salt, user_row["id"]))
                conn.commit()

            conn.close()

            # Success login
            token = secrets.token_hex(24)
            now = datetime.now()
            user_info = {
                "id": user_row["id"],
                "full_name": user_row["full_name"],
                "email": user_row["email"],
                "role": user_row["role"],
                "designation": user_row["designation"] if user_row["designation"] else "Not provided",
                "created_at": now.isoformat(),
                "expires_at": now + timedelta(hours=SESSION_TTL_HOURS)
            }
            SESSIONS[token] = user_info

            log_audit_event(
                user_id=user_row["id"],
                email=user_row["email"],
                event_type="SESSION_LOGIN",
                status="SUCCESS",
                details=f"User authenticated successfully via Local Credential Datastore. Active role: {user_row['role']}"
            )

            extra_headers = {
                "Set-Cookie": f"session_token={token}; Path=/; HttpOnly; SameSite=Lax"
            }
            self.send_json(200, {
                "message": "Login successful",
                "token": token,
                "user": {
                    "id": user_info["id"],
                    "full_name": user_info["full_name"],
                    "email": user_info["email"],
                    "role": user_info["role"],
                    "designation": user_info["designation"]
                }
            }, extra_headers)
            return

        # /api/auth/logout
        if path == "/api/auth/logout":
            user, token = get_current_user(self.headers)
            if token and token in SESSIONS:
                log_audit_event(
                    user_id=user["id"],
                    email=user["email"],
                    event_type="LOGOUT",
                    status="SUCCESS",
                    details="User terminated authenticated session"
                )
                del SESSIONS[token]
            extra_headers = {
                "Set-Cookie": "session_token=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT"
            }
            self.send_json(200, {"message": "Logged out successfully"}, extra_headers)
            return

        # Authenticated endpoints check
        user, _ = get_current_user(self.headers)
        if not user:
            self.send_error_json(401, "Authentication required. Please sign in.", "ERR_UNAUTHORIZED")
            return

        # /api/alerts/<id_or_record_id>/review - REVIEWER or ADMIN
        if path.startswith("/api/alerts/") and path.endswith("/review"):
            if user["role"] not in ("admin", "reviewer"):
                self.send_error_json(403, "Forbidden: Only Reviewers and Admins can update alert statuses or add review notes.", "ERR_FORBIDDEN")
                return

            alert_ident = path[len("/api/alerts/"):len(path) - len("/review")].strip("/")
            new_status = (data.get("status") or "").strip()
            notes = (data.get("notes") or "").strip()

            valid_statuses = ("Open Review", "In Verification", "Action Recommended", "Resolved")
            if new_status not in valid_statuses:
                self.send_error_json(400, f"Invalid status '{new_status}'. Allowed: {', '.join(valid_statuses)}")
                return

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, record_id, waterbody_name, status FROM change_alerts WHERE id = ? OR record_id = ?", (alert_ident, alert_ident))
            alert_row = cursor.fetchone()
            if not alert_row:
                conn.close()
                self.send_error_json(404, f"Alert '{alert_ident}' not found.")
                return

            alert_id = alert_row["id"]
            prev_status = alert_row["status"]
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                UPDATE change_alerts
                SET status = ?, last_reviewed_by = ?, last_reviewed_at = ?, review_notes = ?
                WHERE id = ?
            """, (new_status, user["email"], now_str, notes, alert_id))

            cursor.execute("""
                INSERT INTO alert_reviews (alert_id, reviewer_email, reviewer_name, previous_status, new_status, notes, reviewed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (alert_id, user["email"], user["full_name"], prev_status, new_status, notes, now_str))

            conn.commit()
            conn.close()

            log_audit_event(
                user_id=user["id"],
                email=user["email"],
                event_type="ALERT_REVIEW_RECORDED",
                status="SUCCESS",
                details=f"Alert {alert_id} ({alert_row['waterbody_name']}) status changed from '{prev_status}' to '{new_status}'. Notes recorded."
            )

            self.send_json(200, {
                "message": f"Alert {alert_id} successfully updated to '{new_status}'.",
                "alert_id": alert_id,
                "status": new_status,
                "last_reviewed_by": user["email"],
                "last_reviewed_at": now_str,
                "notes": notes
            })
            return

        # /api/users (Add new workspace user) - ADMIN ONLY
        if path == "/api/users":
            if user["role"] != "admin":
                self.send_error_json(403, "Forbidden: Only authenticated administrators can create accounts.", "ERR_FORBIDDEN")
                return

            full_name = (data.get("full_name") or "").strip()
            email = (data.get("email") or "").strip().lower()
            role = (data.get("role") or "").strip().lower()
            password = data.get("password") or ""
            designation = (data.get("designation") or "").strip()

            if not full_name:
                self.send_error_json(400, "Full name is required", "ERR_VALIDATION_NAME")
                return
            if not email or "@" not in email or "." not in email:
                self.send_error_json(400, "A valid official email address is required", "ERR_VALIDATION_EMAIL")
                return
            if role not in ("admin", "reviewer", "viewer"):
                self.send_error_json(400, "Role must be Admin, Reviewer, or Viewer", "ERR_VALIDATION_ROLE")
                return
            if len(password) < 8:
                self.send_error_json(400, "Temporary password must be at least 8 characters in length", "ERR_VALIDATION_PASSWORD")
                return

            p_hash, salt = hash_password(password)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO users (full_name, email, role, designation, password_hash, salt, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (full_name, email, role, designation or None, p_hash, salt, now))
                new_id = cursor.lastrowid
                conn.commit()
            except sqlite3.IntegrityError:
                conn.close()
                self.send_error_json(400, f"An account with email '{email}' already exists in the workspace.", "ERR_DUPLICATE_EMAIL")
                return
            conn.close()

            log_audit_event(
                user_id=user["id"],
                email=user["email"],
                event_type="USER_PROVISIONED",
                status="SUCCESS",
                details=f"Admin {user['email']} provisioned new user {email} with role: {role}"
            )

            self.send_json(201, {
                "message": "User account created successfully",
                "user": {
                    "id": new_id,
                    "full_name": full_name,
                    "email": email,
                    "role": role,
                    "designation": designation if designation else "Not provided",
                    "created_at": now
                }
            })
            return

        # /api/spatial/validate - REVIEWER or ADMIN
        if path == "/api/spatial/validate":
            if user["role"] not in ("admin", "reviewer"):
                self.send_error_json(403, "Forbidden: Only Reviewers and Admins can validate spatial datasets.", "ERR_FORBIDDEN")
                return

            raw_content = data.get("content", "")
            file_name = data.get("filename", "unknown_file")
            file_format = data.get("format", "").lower()

            if not raw_content:
                self.send_error_json(400, "Empty file content received.")
                return

            validation_result = self.validate_spatial_data(raw_content, file_name, file_format)
            self.send_json(200, validation_result)
            return

        # /api/spatial/commit - REVIEWER or ADMIN
        if path == "/api/spatial/commit":
            if user["role"] not in ("admin", "reviewer"):
                self.send_error_json(403, "Forbidden: Only Reviewers and Admins can commit spatial datasets.", "ERR_FORBIDDEN")
                return

            records = data.get("records", [])
            crs = data.get("crs", "EPSG:4326")

            if not records:
                self.send_error_json(400, "No records provided for commit.")
                return

            committed_count, updated_count, errors = self.commit_spatial_records(records, crs, user)
            self.send_json(200, {
                "message": f"Successfully ingested {committed_count} new and updated {updated_count} cadastral records.",
                "committed_count": committed_count,
                "updated_count": updated_count,
                "errors": errors
            })
            return

        self.send_error_json(404, f"API route not found: {path}")

    def validate_spatial_data(self, content, filename, format_hint):
        errors = []
        warnings = []
        valid_records = []
        detected_crs = "EPSG:4326 (WGS 84)"
        crs_supported = True

        is_json = False
        parsed_json = None

        if format_hint in ("geojson", "json") or filename.endswith((".geojson", ".json")):
            try:
                parsed_json = json.loads(content)
                is_json = True
            except Exception as e:
                errors.append(f"Invalid JSON syntax: {str(e)}")
                return {
                    "valid": False,
                    "filename": filename,
                    "record_count": 0,
                    "detected_crs": "Unknown",
                    "crs_supported": False,
                    "errors": errors,
                    "warnings": warnings,
                    "sample_records": []
                }

        if is_json and parsed_json:
            # Check CRS in GeoJSON
            if "crs" in parsed_json:
                crs_name = ""
                try:
                    crs_name = parsed_json["crs"]["properties"]["name"]
                except Exception:
                    crs_name = str(parsed_json["crs"])

                if "CRS84" in crs_name or "4326" in crs_name:
                    detected_crs = "EPSG:4326 (WGS 84)"
                    crs_supported = True
                else:
                    detected_crs = crs_name
                    crs_supported = False
                    errors.append(f"Unsupported Coordinate Reference System '{crs_name}'. NeerWatch requires standard WGS 84 (EPSG:4326). Coordinates will not be silently reprojected.")

            features = []
            if parsed_json.get("type") == "FeatureCollection" and "features" in parsed_json:
                features = parsed_json["features"]
            elif parsed_json.get("type") == "Feature":
                features = [parsed_json]
            elif isinstance(parsed_json, list):
                features = parsed_json
            else:
                warnings.append("Expected FeatureCollection or Feature list; attempting generic object parsing.")
                features = [parsed_json]

            rec_index = 0
            for feat in features:
                rec_index += 1
                props = feat.get("properties", feat) if isinstance(feat, dict) else {}
                geom = feat.get("geometry") if isinstance(feat, dict) else None

                rec_id = props.get("record_id") or props.get("id") or props.get("wb_id") or props.get("waterbody_id") or f"CMA-WB-IMP-{rec_index:03d}"
                name = props.get("waterbody_name") or props.get("name") or props.get("wb_name") or props.get("title") or f"Unnamed Water Body {rec_index}"
                zone = props.get("zone") or props.get("taluk") or props.get("district") or props.get("location") or "Chennai Metro Area"
                area = props.get("area_hectares") or props.get("area_ha") or props.get("area") or props.get("extent_ha") or 0.0

                try:
                    area = float(area)
                except Exception:
                    area = 0.0
                    warnings.append(f"Row {rec_index} ({rec_id}): invalid area format, defaulted to 0.0 ha.")

                geom_valid = False
                if geom and isinstance(geom, dict):
                    g_type = geom.get("type")
                    coords = geom.get("coordinates")
                    if g_type in ("Polygon", "MultiPolygon", "Point", "LineString") and coords:
                        geom_valid = True

                if not geom_valid:
                    errors.append(f"Feature {rec_index} ({name}): missing or invalid GeoJSON geometry.")
                else:
                    valid_records.append({
                        "record_id": str(rec_id),
                        "waterbody_name": str(name),
                        "zone": str(zone),
                        "area_hectares": area,
                        "geometry": geom,
                        "raw_properties": props
                    })

        elif format_hint == "csv" or filename.endswith(".csv"):
            detected_crs = "EPSG:4326 (WGS 84 Coordinates)"
            try:
                reader = csv.DictReader(io.StringIO(content))
                rows = list(reader)
                rec_index = 0
                for r in rows:
                    rec_index += 1
                    rec_id = r.get("record_id") or r.get("id") or r.get("wb_id") or f"CMA-WB-CSV-{rec_index:03d}"
                    name = r.get("waterbody_name") or r.get("name") or r.get("wb_name") or f"Water Body {rec_index}"
                    zone = r.get("zone") or r.get("taluk") or r.get("location") or "Chennai Metro Area"
                    area = r.get("area_hectares") or r.get("area_ha") or r.get("area") or 0.0

                    try:
                        area = float(area)
                    except Exception:
                        area = 0.0

                    lat = r.get("latitude") or r.get("lat") or r.get("y")
                    lng = r.get("longitude") or r.get("lng") or r.get("lon") or r.get("x")
                    geom_str = r.get("geometry") or r.get("geom")

                    geom = None
                    if geom_str:
                        try:
                            geom = json.loads(geom_str)
                        except Exception:
                            pass

                    if not geom and lat and lng:
                        try:
                            f_lat = float(lat)
                            f_lng = float(lng)
                            geom = {"type": "Point", "coordinates": [f_lng, f_lat]}
                        except Exception:
                            pass

                    if not geom:
                        errors.append(f"CSV Row {rec_index} ({name}): Could not find valid lat/lng coordinates or GeoJSON geometry string.")
                    else:
                        valid_records.append({
                            "record_id": str(rec_id),
                            "waterbody_name": str(name),
                            "zone": str(zone),
                            "area_hectares": area,
                            "geometry": geom,
                            "raw_properties": r
                        })
            except Exception as e:
                errors.append(f"CSV parsing failed: {str(e)}")
        else:
            errors.append(f"Unsupported file format: {filename}. Supported formats: GeoJSON (.geojson, .json), CSV (.csv).")

        return {
            "valid": len(errors) == 0 and crs_supported and len(valid_records) > 0,
            "filename": filename,
            "record_count": len(valid_records) + len(errors),
            "valid_count": len(valid_records),
            "error_count": len(errors),
            "detected_crs": detected_crs,
            "crs_supported": crs_supported,
            "errors": errors[:10],
            "warnings": warnings[:10],
            "sample_records": valid_records[:5],
            "records": valid_records
        }

    def commit_spatial_records(self, records, crs, user):
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        committed = 0
        updated = 0
        errors = []

        for rec in records:
            rec_id = rec.get("record_id")
            name = rec.get("waterbody_name")
            zone = rec.get("zone")
            area = rec.get("area_hectares", 0.0)
            geom = rec.get("geometry")
            geom_str = json.dumps(geom) if isinstance(geom, dict) else str(geom)

            try:
                cursor.execute("SELECT id FROM water_bodies WHERE record_id = ?", (rec_id,))
                existing = cursor.fetchone()
                if existing:
                    cursor.execute("""
                        UPDATE water_bodies
                        SET waterbody_name = ?, zone = ?, area_hectares = ?, geometry = ?, crs = ?, updated_at = ?
                        WHERE record_id = ?
                    """, (name, zone, area, geom_str, crs, now, rec_id))
                    updated += 1
                else:
                    cursor.execute("""
                        INSERT INTO water_bodies (record_id, waterbody_name, zone, area_hectares, geometry, crs, status, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, 'Monitored', ?, ?)
                    """, (rec_id, name, zone, area, geom_str, crs, now, now))
                    committed += 1
            except Exception as e:
                errors.append(f"Failed to save {rec_id}: {str(e)}")

        conn.commit()
        conn.close()

        log_audit_event(
            user_id=user["id"],
            email=user["email"],
            event_type="SPATIAL_INGEST_COMMIT",
            status="SUCCESS" if not errors else "PARTIAL",
            details=f"Committed {committed} new, updated {updated} cadastral records. CRS: {crs}"
        )

        return committed, updated, errors

    def serve_static_file(self, req_path):
        if req_path == "/" or req_path == "":
            req_path = "/index.html"

        clean_path = os.path.normpath(req_path.lstrip("/"))
        file_path = os.path.join(PUBLIC_DIR, clean_path)

        if not os.path.abspath(file_path).startswith(os.path.abspath(PUBLIC_DIR)):
            self.send_error_json(403, "Access denied")
            return

        if not os.path.isfile(file_path):
            index_path = os.path.join(PUBLIC_DIR, "index.html")
            if os.path.isfile(index_path):
                file_path = index_path
            else:
                self.send_error_json(404, "File not found")
                return

        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or "application/octet-stream"

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", f"{mime_type}; charset=utf-8" if "text" in mime_type or "json" in mime_type or "javascript" in mime_type else mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error_json(500, f"Error reading file: {str(e)}")

def run_server():
    init_db()
    server = socketserver.TCPServer(("127.0.0.1", PORT), NeerWatchRequestHandler)
    print("==================================================")
    print(f" NeerWatch Cadastral Server running on http://127.0.0.1:{PORT}")
    print(" Active Database: " + get_db_path())
    print("==================================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down NeerWatch server...")
        server.server_close()

if __name__ == "__main__":
    run_server()
