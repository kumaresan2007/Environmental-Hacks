# NeerWatch — Chennai Water Bodies Surveillance GIS Workspace

> **Civic GIS Platform for Chennai Metro Area (CMA) Water Resources Cadastral Surveillance**  
> Developed for Tamil Nadu Water Resources Department & CMA Cadastral GIS.

---

## 1. Overview & Architecture

NeerWatch is a civic cadastral GIS administration and surveillance workspace built to inspect water bodies, monitor satellite change alerts (such as encroachments and water spread contraction), manage personnel authorizations, and ingest/export spatial datasets.

The system is implemented as:
- **Frontend**: Standalone HTML5, Vanilla CSS3, and ES6 JavaScript utilizing the Civic GIS design system.
- **Backend**: Python standard-library HTTP server (`http.server`, `urllib`, `hashlib`, `secrets`, `json`, `csv`) requiring **no external pip dependencies**.
- **Database**: SQLite3 (`neerwatch.db`) providing persistence for personnel, waterbody cadastral polygons, change alerts, review history, and immutable authentication audit logs.

---

## 2. Visual Language & Workspace Design

The user interface adheres to a clean, government-grade Civic GIS design language:

| Design Element | Specification & Values |
| :--- | :--- |
| **Page Background** | Pale mint `#EBFDF9` |
| **Headers & Panels** | Light mint `#E5F8F3` with crisp white card surfaces |
| **Primary Controls** | Deep teal `#0D5C58` (normal) and `#004340` (hover/active) |
| **Primary Text** | Dark `#0E1E1C` |
| **Secondary Text** | Slate `#3F4947` |
| **Borders** | Subtle `#BEC9C7` and `#D1DCDA` |
| **Status Indicators** | Green `#107C41` (Nominal / Monitored / Authorized), Amber `#996500` (Review / In Verification), Red `#C42B1C` (High Severity Alert) |
| **Typography** | **Public Sans** for clean UI interfaces, **JetBrains Mono** for technical metadata (EPSG codes, record IDs, coordinates, timestamps) |
| **Geometry & Elevation**| Flat surfaces, thin 1px borders, compact 4px/6px border radii, restrained elevation shadows |
| **Desktop Layout** | 256px fixed left sidebar, top application bar, responsive two-column information-dense layout |
| **Responsive Design** | Collapsible sidebar drawer for tablet/mobile; responsive stacking without clipping tables or controls |

---

## 3. How to Start the Application

### Prerequisites
- Python 3.10+ (Built & tested with Python 3.12)
- Any modern web browser (Edge, Chrome, Firefox)

### Step 1: Initialize / Migrate the Database (Safe & Non-Destructive)
```powershell
python database.py
```
*Note: Preserves all existing records, users, geometries, alerts, and audit history.*

### Step 2: Start the NeerWatch Server
```powershell
python server.py
```
The server will start on `http://127.0.0.1:8080`.

### Step 3: Open in Browser
Visit:
```
http://127.0.0.1:8080/
```

---

## 4. Available Sections & Workflows

NeerWatch provides 7 integrated workspace sections accessible via the left sidebar navigation:

1. **Dashboard (`#dashboard`)**
   - Live summary metrics: Monitored Water Bodies, Total Area Extent (ha), Active Change Alerts, and Areas Under Active Review.
   - Priority alerts table with instant "Review Alert" action.
   - Unified chronological workspace activity feed (logins, alert reviews, spatial commits).
   - Zonal distribution breakdown of water spread extents.

2. **Water Bodies Inventory (`#waterbodies`)**
   - Searchable and filterable table of registered lakes, reservoirs, and tanks.
   - Filters: Search by name or record ID, Zone filter, Surveillance status filter.
   - Record Detail Modal: View geometry summary, vertices count, area metrics, active alerts, and direct link to focus on the GIS Map.

3. **Change Surveillance Alerts (`#alerts`)**
   - Filter and sort by Severity (`High`, `Medium`, `Low`), Status (`Open Review`, `In Verification`, `Action Recommended`, `Resolved`), Zone, and Detection Date.
   - Alert cards displaying satellite contraction percentage, detection dates, and reviewer commentary..
   - **Review Alert Modal**: Authorized Reviewers and Admins can update verification status and record inspection notes with an immutable audit trail.

4. **GIS Spatial Map View (`#map`)**
   - Interactive spatial vector canvas rendering real stored water body polygons and alert locations in WGS 84 (EPSG:4326).
   - Controls: Zoom In, Zoom Out, Reset, Jump to Water Body dropdown, Toggle Polygons, Toggle Alert Pins.
   - GIS Legend indicating monitored water bodies, lakes with alerts, and severity pin overlays.

5. **Spatial Data Ingestion (`#import`)**
   - 3-step guided spatial ingestion workflow:
     1. Drag-and-drop or select GeoJSON (`.geojson`, `.json`) or CSV (`.csv`) survey files.
     2. Instant validation: Checks declared CRS against WGS 84 (EPSG:4326), validates geometry conformity, and resolves property aliases (`record_id`, `waterbody_name`, `zone`, `area_hectares`, `geometry`).
     3. Pre-commit review table previewing valid records with Cancel and Confirm & Commit actions.
   - 1-Click test samples: "Load Sample GeoJSON" and "Load Sample CSV".

6. **Reports & Exports (`#reports`)**
   - Cadastral Dataset Export Hub with cycle and zone filters:
     - **Cadastral Water Bodies (GeoJSON)**: Boundary polygons in EPSG:4326 (`/api/export/waterbodies.geojson`).
     - **Water Bodies Inventory (CSV)**: Tabular inventory with areas and zones (`/api/export/waterbodies.csv`).
     - **Surveillance Change Alerts (CSV)**: Alerts, severity, and reviewer notes (`/api/export/alerts.csv`).
     - **Executive Cadastral Digest (Printable PDF/HTML)**: Official summary report with surveillance metrics and audit stamps (`/api/export/digest.pdf`).

7. **Administration (`#admin`)**
   - User Management: Live user statistics, searchable personnel directory, and role badges.
   - Provision Authorized User Modal (Admin only): Creates user accounts with validated name, official email, role, and temporary password (min. 8 characters).
   - Immutable server-side authentication audit log (`audit_logins`).
   - Role Authority & Permissions Reference Matrix.
   - Integrations & Compliance Verification panel.

---

## 5. Role-Based Access Control & Backend Enforcement

The backend strictly verifies roles on all sensitive endpoints. The UI includes a session switcher in the top bar to easily test different roles:

| Workspace Role | Allowed Capabilities | Restricted Capabilities (Enforced with HTTP 403) |
| :--- | :--- | :--- |
| **Viewer** | View dashboard, water bodies, alerts, map, and export permitted datasets. | Updating alert statuses, recording review notes, importing spatial datasets, and provisioning users. |
| **Reviewer** | All Viewer capabilities plus reviewing change alerts, recording inspection notes, and validating/committing spatial datasets. | User account provisioning and administrative settings. |
| **Admin** | Full workspace authority: user provisioning, role assignments, alert reviews, spatial commits, and unrestricted exports. | None. |

> **Role Simulator Notice**: The role simulator in the top bar provides an optional visual preview of how UI elements render for different roles. Real permissions are cryptographically enforced on the server for all write/commit actions.

---

## 6. Security & Data Integrity

- **Password Hashing**: Implemented using Python's standard-library `hashlib.pbkdf2_hmac('sha256', ...)` with 100,000 iterations and cryptographic salts. Constant-time comparison via `secrets.compare_digest` prevents timing attacks. Legacy hashes are automatically upgraded to PBKDF2 upon sign-in.
- **Session Tokens**: 24-byte cryptographic tokens (`secrets.token_hex`) with a 24-hour expiration lifetime.
- **CORS Protection**: Restricted to same-origin and verified local loopback requests. Wildcard CORS headers are strictly avoided.
- **Data Protection**: Existing application data in `neerwatch.db` is preserved and protected. Automated tests operate against isolated database copies (`neerwatch_test_run.db`) and never touch production records.
- **Honest Integration Reporting**: Integrations not yet connected (such as LDAP directory synchronization or hardware biometric modules) are truthfully displayed as **"Not configured"**.

---

## 7. Automated Test Suite

To run the complete automated test suite:
```powershell
python test_endpoints.py
```

The test runner:
1. Copies `neerwatch.db` to an isolated temporary test database.
2. Launches an ephemeral test instance on a dedicated test port.
3. Tests dashboard metrics, authentication, water body filtering, alert reviews, role restrictions (403), user provisioning (400 on short password, 201 on success), spatial ingestion, and all 4 export formats.
4. Cleans up and deletes the temporary test database upon completion.
