"""
NeerWatch Database Module
SQLite datastore for CMA (Chennai Metro Area) Cadastral GIS & Water Resources workspace.
Includes schema migration, secure PBKDF2 password hashing, and test database isolation.
"""

import sqlite3
import hashlib
import secrets
import os
import json
from datetime import datetime

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "neerwatch.db")

def get_db_path():
    return os.environ.get("NEERWATCH_DB_PATH", DEFAULT_DB_PATH)

def get_db_connection(db_path=None):
    target_path = db_path or get_db_path()
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    """
    Secure password hashing using PBKDF2-HMAC-SHA256 with 100,000 iterations and salt.
    """
    if not salt:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    formatted_hash = f"pbkdf2:sha256:100000${salt}${dk.hex()}"
    return formatted_hash, salt

def verify_password(password: str, salt: str, password_hash: str) -> bool:
    """
    Verifies password using constant-time comparison.
    Supports PBKDF2 hashes and legacy SHA-256 hashes seamlessly.
    """
    if password_hash.startswith("pbkdf2:"):
        parts = password_hash.split("$")
        if len(parts) == 3:
            _, h_salt, h_hash = parts
            dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), h_salt.encode('utf-8'), 100000)
            return secrets.compare_digest(dk.hex(), h_hash)
    
    # Legacy SHA-256 fallback for existing database accounts
    legacy_hash = hashlib.sha256((salt + password).encode('utf-8')).hexdigest()
    return secrets.compare_digest(legacy_hash, password_hash)

def needs_hash_upgrade(password_hash: str) -> bool:
    """Returns True if the stored hash uses the legacy format and should be upgraded."""
    return not password_hash.startswith("pbkdf2:")

def run_migrations(conn):
    """
    Preserves all existing data and safely applies schema additions.
    """
    cursor = conn.cursor()

    # 1. Base Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'reviewer', 'viewer')),
            designation TEXT,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # 2. Immutable Audit Logins table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            email TEXT NOT NULL,
            event_type TEXT NOT NULL,
            status TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            details TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    # 3. Water Bodies table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS water_bodies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id TEXT UNIQUE NOT NULL,
            waterbody_name TEXT NOT NULL,
            zone TEXT NOT NULL,
            area_hectares REAL NOT NULL,
            geometry TEXT NOT NULL,
            crs TEXT DEFAULT 'EPSG:4326',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # Check and add 'status' to water_bodies if missing
    cursor.execute("PRAGMA table_info(water_bodies)")
    wb_cols = [r["name"] for r in cursor.fetchall()]
    if "status" not in wb_cols:
        cursor.execute("ALTER TABLE water_bodies ADD COLUMN status TEXT DEFAULT 'Monitored'")

    # 4. Change Alerts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS change_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id TEXT NOT NULL,
            waterbody_name TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            cycle TEXT NOT NULL,
            status TEXT NOT NULL,
            detected_at TEXT NOT NULL,
            area_change_pct REAL,
            details TEXT
        )
    """)

    # Check and add review tracking columns to change_alerts if missing
    cursor.execute("PRAGMA table_info(change_alerts)")
    alert_cols = [r["name"] for r in cursor.fetchall()]
    if "last_reviewed_by" not in alert_cols:
        cursor.execute("ALTER TABLE change_alerts ADD COLUMN last_reviewed_by TEXT")
    if "last_reviewed_at" not in alert_cols:
        cursor.execute("ALTER TABLE change_alerts ADD COLUMN last_reviewed_at TEXT")
    if "review_notes" not in alert_cols:
        cursor.execute("ALTER TABLE change_alerts ADD COLUMN review_notes TEXT")

    # 5. Alert Reviews History table (tracks every note and status change)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alert_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id INTEGER NOT NULL,
            reviewer_email TEXT NOT NULL,
            reviewer_name TEXT NOT NULL,
            previous_status TEXT NOT NULL,
            new_status TEXT NOT NULL,
            notes TEXT NOT NULL,
            reviewed_at TEXT NOT NULL,
            FOREIGN KEY(alert_id) REFERENCES change_alerts(id)
        )
    """)

    conn.commit()

def init_db(db_path=None):
    """
    Initializes database and runs non-destructive migrations.
    Never resets or overwrites existing records.
    """
    conn = get_db_connection(db_path)
    run_migrations(conn)

    # Check if this is an empty fresh database
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]

    if user_count == 0:
        seed_fresh_db(cursor, conn)

    conn.close()

def seed_fresh_db(cursor, conn):
    """
    Seeds initial reference data only when initializing a completely fresh/empty database.
    Does not run if users already exist.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Generate initial credentials dynamically for blank databases
    # Existing neerwatch.db already has its data and will not reach here.
    initial_accounts = [
        ("Dr. K. Ramanathan", "k.ramanathan@cma.tn.gov.in", "admin", "Principal Geospatial Director", "2026-01-15 09:30:00"),
        ("S. Priya", "s.priya@wrd.tn.gov.in", "reviewer", "Senior Hydro-Cadastral Officer", "2026-02-10 11:15:00"),
        ("M. Arun Kumar", "m.arun@tndma.gov.in", "viewer", "Disaster Management Analyst", "2026-03-01 14:00:00"),
        ("V. Anitha", "v.anitha@cma.tn.gov.in", "reviewer", "GIS Field Surveyor", "2026-04-18 10:20:00"),
        ("R. Selvam", "r.selvam@wrd.tn.gov.in", "viewer", "Water Resources Inspector", "2026-05-22 16:45:00")
    ]

    for name, email, role, designation, created_at in initial_accounts:
        # Generate initial password hash
        init_pass = os.environ.get("INITIAL_ADMIN_SEED_PASS", "NeerWatch@" + secrets.token_hex(4))
        p_hash, salt = hash_password(init_pass)
        cursor.execute("""
            INSERT INTO users (full_name, email, role, designation, password_hash, salt, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, email, role, designation, p_hash, salt, created_at))

    # Water Bodies (Chennai Metro Area) - sample baseline records
    waterbodies = [
        ("CMA-WB-001", "Chembarambakkam Lake", "Sriperumbudur Zone", 2550.0, {
            "type": "Polygon",
            "coordinates": [[[80.015, 13.011], [80.035, 13.025], [80.040, 13.005], [80.020, 12.995], [80.015, 13.011]]]
        }, "2026-01-10 08:00:00"),
        ("CMA-WB-002", "Puzhal Lake (Red Hills)", "Madhavaram Zone", 1820.0, {
            "type": "Polygon",
            "coordinates": [[[80.170, 13.180], [80.190, 13.195], [80.200, 13.170], [80.175, 13.160], [80.170, 13.180]]]
        }, "2026-01-10 08:00:00"),
        ("CMA-WB-003", "Porur Lake", "Valasaravakkam Zone", 202.4, {
            "type": "Polygon",
            "coordinates": [[[80.145, 13.030], [80.160, 13.040], [80.165, 13.025], [80.150, 13.020], [80.145, 13.030]]]
        }, "2026-01-10 08:00:00"),
        ("CMA-WB-004", "Velachery Lake", "Velachery Zone", 26.5, {
            "type": "Polygon",
            "coordinates": [[[80.210, 12.975], [80.220, 12.980], [80.222, 12.970], [80.212, 12.968], [80.210, 12.975]]]
        }, "2026-01-10 08:00:00"),
        ("CMA-WB-005", "Sholinganallur Wetland", "Sholinganallur Zone", 142.8, {
            "type": "Polygon",
            "coordinates": [[[80.225, 12.900], [80.240, 12.910], [80.245, 12.895], [80.230, 12.890], [80.225, 12.900]]]
        }, "2026-01-10 08:00:00"),
        ("CMA-WB-006", "Ambattur Lake", "Ambattur Zone", 200.0, {
            "type": "Polygon",
            "coordinates": [[[80.150, 13.110], [80.165, 13.120], [80.170, 13.105], [80.155, 13.100], [80.150, 13.110]]]
        }, "2026-01-10 08:00:00"),
        ("CMA-WB-007", "Chitlapakkam Lake", "Tambaram Zone", 35.2, {
            "type": "Polygon",
            "coordinates": [[[80.140, 12.935], [80.150, 12.940], [80.152, 12.930], [80.142, 12.928], [80.140, 12.935]]]
        }, "2026-01-10 08:00:00"),
        ("CMA-WB-008", "Pallikaranai Marshland", "South Chennai Zone", 698.0, {
            "type": "Polygon",
            "coordinates": [[[80.205, 12.920], [80.225, 12.935], [80.230, 12.910], [80.210, 12.905], [80.205, 12.920]]]
        }, "2026-01-10 08:00:00")
    ]

    for rec_id, w_name, zone, area, geom, created in waterbodies:
        cursor.execute("""
            INSERT INTO water_bodies (record_id, waterbody_name, zone, area_hectares, geometry, crs, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'EPSG:4326', 'Monitored', ?, ?)
        """, (rec_id, w_name, zone, area, json.dumps(geom), created, created))

    # Real Workspace Change Alerts (Sample satellite surveillance cycle)
    alerts = [
        ("CMA-WB-004", "Velachery Lake", "Encroachment Warning", "High", "2026-Q3", "Open Review", "2026-10-08 11:20:00", -4.2, "Commercial masonry detected encroaching into northern buffer zone boundary."),
        ("CMA-WB-003", "Porur Lake", "Water Spread Contraction", "Medium", "2026-Q3", "Open Review", "2026-10-09 14:15:00", -7.5, "Satellite reflectance indicates 7.5% surface water contraction compared to baseline."),
        ("CMA-WB-007", "Chitlapakkam Lake", "Buffer Zone Violation", "High", "2026-Q3", "In Verification", "2026-10-10 09:40:00", -3.1, "Unauthorized earth filling along eastern bund perimeter."),
        ("CMA-WB-005", "Sholinganallur Wetland", "Vegetation Overgrowth", "Low", "2026-Q3", "Open Review", "2026-10-10 16:50:00", 2.3, "Invasive water hyacinth infestation covering inlet channels."),
        ("CMA-WB-008", "Pallikaranai Marshland", "Boundary Anomaly", "Medium", "2026-Q3", "In Verification", "2026-10-11 10:15:00", -1.8, "Construction debris dumped along perimeter road intersection.")
    ]

    for rec_id, w_name, a_type, severity, cycle, status, det_at, chg_pct, details in alerts:
        cursor.execute("""
            INSERT INTO change_alerts (record_id, waterbody_name, alert_type, severity, cycle, status, detected_at, area_change_pct, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (rec_id, w_name, a_type, severity, cycle, status, det_at, chg_pct, details))

    conn.commit()

if __name__ == "__main__":
    init_db()
    print("Database checked and migrations applied successfully.")
