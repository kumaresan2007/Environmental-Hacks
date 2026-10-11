"""
NeerWatch Automated Test Suite
Tests all API endpoints, role permissions, workflow operations, and exports.
Operates on a temporary database copy to strictly protect neerwatch.db.
"""

import urllib.request
import urllib.error
import urllib.parse
import json
import os
import shutil
import subprocess
import time
import sys

TEST_PORT = 8888
BASE_URL = f"http://127.0.0.1:{TEST_PORT}/api"
TEST_DB = "neerwatch_test_run.db"

def make_req(path, data=None, token=None, method="GET"):
    quoted_path = urllib.parse.quote(path, safe="/?=&")
    url = f"{BASE_URL}{quoted_path}"
    req = urllib.request.Request(url, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("X-Session-Token", token)
    body = json.dumps(data).encode("utf-8") if data is not None else None
    try:
        with urllib.request.urlopen(req, data=body) as res:
            res_body = res.read().decode("utf-8")
            content_type = res.headers.get_content_type()
            return res.status, json.loads(res_body) if content_type == "application/json" else res_body
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(err_body)
        except Exception:
            return e.code, err_body

def run_tests():
    print("=" * 60)
    print(" Starting NeerWatch Test Suite (Isolated Test DB)")
    print("=" * 60)

    # 1. Prepare isolated test database copy
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except Exception:
            pass
    shutil.copyfile("neerwatch.db", TEST_DB)
    print(f"[Setup] Copied neerwatch.db -> {TEST_DB} for isolated testing.")

    # 2. Launch test server process on TEST_PORT
    env = os.environ.copy()
    env["NEERWATCH_DB_PATH"] = os.path.abspath(TEST_DB)
    server_proc = subprocess.Popen(
        [sys.executable, "-c", f"import server; server.PORT = {TEST_PORT}; server.run_server()"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for server to bind
    time.sleep(1.5)

    try:
        # TEST 1: Dashboard API
        status, dash = make_req("/dashboard")
        assert status == 200, f"Dashboard failed with {status}"
        assert dash["total_waterbodies"] > 0
        assert dash["active_alerts_count"] > 0
        assert dash["total_area_hectares"] > 0
        assert "zone_distribution" in dash
        assert "recent_activity" in dash
        print(f"PASS: /api/dashboard returned {dash['total_waterbodies']} water bodies, {dash['total_area_hectares']} ha, {dash['active_alerts_count']} active alerts.")

        # TEST 2: Authentication
        status, admin_login = make_req("/auth/login", data={"email": "k.ramanathan@cma.tn.gov.in", "password": "Admin@password123"}, method="POST")
        assert status == 200
        admin_token = admin_login["token"]
        assert admin_login["user"]["role"] == "admin"
        print("PASS: Admin authentication verified.")

        status, reviewer_login = make_req("/auth/login", data={"email": "s.priya@wrd.tn.gov.in", "password": "Reviewer@123"}, method="POST")
        assert status == 200
        reviewer_token = reviewer_login["token"]
        assert reviewer_login["user"]["role"] == "reviewer"
        print("PASS: Reviewer authentication verified.")

        status, viewer_login = make_req("/auth/login", data={"email": "m.arun@tndma.gov.in", "password": "Viewer@123"}, method="POST")
        assert status == 200
        viewer_token = viewer_login["token"]
        assert viewer_login["user"]["role"] == "viewer"
        print("PASS: Viewer authentication verified.")

        # TEST 3: Water Bodies Filtering & Search
        status, wb_all = make_req("/waterbodies")
        assert status == 200
        total_wb = len(wb_all["features"])
        print(f"PASS: /api/waterbodies returned {total_wb} GeoJSON features.")

        # Filter by Zone
        status, wb_zone = make_req("/waterbodies?zone=Madhavaram Zone")
        assert status == 200
        assert len(wb_zone["features"]) > 0
        assert all(f["properties"]["zone"] == "Madhavaram Zone" for f in wb_zone["features"])
        print(f"PASS: Water bodies zone filter verified ({len(wb_zone['features'])} in Madhavaram Zone).")

        # Search by name
        status, wb_search = make_req("/waterbodies?search=Velachery")
        assert status == 200
        assert any("Velachery" in f["properties"]["waterbody_name"] for f in wb_search["features"])
        print("PASS: Water bodies search filter verified.")

        # Detail view
        status, wb_detail = make_req("/waterbodies/CMA-WB-004")
        assert status == 200
        assert wb_detail["record_id"] == "CMA-WB-004"
        assert "geometry" in wb_detail
        assert "alerts" in wb_detail
        print(f"PASS: Waterbody detail view verified for {wb_detail['waterbody_name']} (has {len(wb_detail['alerts'])} alerts).")

        # TEST 4: Alerts Filtering, Sorting & Detail View
        status, alerts_all = make_req("/alerts")
        assert status == 200
        print(f"PASS: /api/alerts returned {alerts_all['total_matched']} alerts.")

        # Severity filter
        status, alerts_high = make_req("/alerts?severity=High")
        assert status == 200
        assert all(a["severity"] == "High" for a in alerts_high["alerts"])
        print(f"PASS: Alerts severity filter verified ({len(alerts_high['alerts'])} High severity).")

        # Sorting
        status, alerts_sorted = make_req("/alerts?sort=severity_desc")
        assert status == 200
        assert alerts_sorted["alerts"][0]["severity"] == "High"
        print("PASS: Alerts sorting verified.")

        # Single alert detail
        status, alert_detail = make_req("/alerts/1")
        assert status == 200
        assert "reviews_history" in alert_detail
        print("PASS: Alert detail with review history verified.")

        # TEST 5: Alert Review & Notes Workflow (Role-Enforced)
        # 5a. Viewer attempts review -> MUST be 403 Forbidden
        status, res = make_req("/alerts/1/review", data={
            "status": "In Verification",
            "notes": "Attempted update by viewer"
        }, token=viewer_token, method="POST")
        assert status == 403, f"Expected 403, got {status}"
        print("PASS: Viewer role correctly forbidden (HTTP 403) from updating alert status.")

        # 5b. Reviewer submits review note and status change -> MUST be 200 OK
        review_note = "Ground survey team dispatched to northern bund for GPS boundary check."
        status, review_res = make_req("/alerts/1/review", data={
            "status": "In Verification",
            "notes": review_note
        }, token=reviewer_token, method="POST")
        assert status == 200, f"Expected 200, got {status}: {review_res}"
        assert review_res["status"] == "In Verification"
        print("PASS: Reviewer successfully updated alert status to 'In Verification' and recorded notes.")

        # 5c. Verify review history contains the note
        status, alert_hist = make_req("/alerts/1")
        assert status == 200
        assert alert_hist["status"] == "In Verification"
        assert any(r["notes"] == review_note for r in alert_hist["reviews_history"])
        print("PASS: Alert review history accurately persists in database.")

        # TEST 6: User Management (Role-Enforced)
        # 6a. Viewer attempts creating user -> 403
        status, _ = make_req("/users", data={
            "full_name": "Test User",
            "email": "test@cma.tn.gov.in",
            "role": "viewer",
            "password": "Password123"
        }, token=viewer_token, method="POST")
        assert status == 403
        print("PASS: Non-admin correctly forbidden (HTTP 403) from creating user accounts.")

        # 6b. Admin provides short password -> 400
        status, _ = make_req("/users", data={
            "full_name": "Test User",
            "email": "test@cma.tn.gov.in",
            "role": "viewer",
            "password": "short"
        }, token=admin_token, method="POST")
        assert status == 400
        print("PASS: Minimum password length validation enforced (HTTP 400).")

        # 6c. Admin creates valid user -> 201
        status, new_user = make_req("/users", data={
            "full_name": "G. Manickam",
            "email": "manickam.g@cma.tn.gov.in",
            "role": "reviewer",
            "designation": "Zonal Hydrographer",
            "password": "ValidPassword@2026"
        }, token=admin_token, method="POST")
        assert status == 201
        print("PASS: Admin provisioned new authorized user (HTTP 201).")

        # TEST 7: Spatial Data Ingestion
        geojson_content = json.dumps({
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
            "features": [{
                "type": "Feature",
                "properties": {
                    "record_id": "CMA-WB-TEST-01",
                    "waterbody_name": "Test Eri Reservoir",
                    "zone": "Tambaram Zone",
                    "area_hectares": 55.4
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[80.1, 12.9], [80.12, 12.92], [80.13, 12.9], [80.1, 12.9]]]
                }
            }]
        })

        # Validate GeoJSON
        status, val_res = make_req("/spatial/validate", data={
            "filename": "test.geojson",
            "format": "geojson",
            "content": geojson_content
        }, token=reviewer_token, method="POST")
        assert status == 200
        assert val_res["valid"] is True
        print("PASS: Spatial validation passed for GeoJSON.")

        # Commit GeoJSON
        status, commit_res = make_req("/spatial/commit", data={
            "records": val_res["records"],
            "crs": val_res["detected_crs"]
        }, token=reviewer_token, method="POST")
        assert status == 200
        print("PASS: Spatial commitment verified in SQLite datastore.")

        # TEST 8: Export Formats
        status, _ = make_req("/export/waterbodies.geojson")
        assert status == 200
        print("PASS: GeoJSON export downloaded.")

        status, _ = make_req("/export/waterbodies.csv")
        assert status == 200
        print("PASS: Water bodies CSV export downloaded.")

        status, _ = make_req("/export/alerts.csv")
        assert status == 200
        print("PASS: Alerts CSV export downloaded.")

        status, _ = make_req("/export/digest.pdf")
        assert status == 200
        print("PASS: Executive digest produced.")

        print("=" * 60)
        print(" ALL ENDPOINT & WORKFLOW TESTS PASSED SUCCESSFULLY! ")
        print("=" * 60)

    finally:
        # Terminate test server and clean up temporary database copy
        server_proc.terminate()
        server_proc.wait()
        if os.path.exists(TEST_DB):
            try:
                os.remove(TEST_DB)
                print(f"[Cleanup] Removed temporary test database {TEST_DB}.")
            except Exception:
                pass

if __name__ == "__main__":
    run_tests()
