/**
 * NeerWatch GIS Workspace Interactive Controller
 * Complete support for Dashboard, Water Bodies, Change Alerts, GIS Map, Data Import, Reports & Admin.
 */

document.addEventListener('DOMContentLoaded', () => {
  const state = {
    currentSection: 'dashboard',
    currentUser: null,
    simulatedRole: 'actual', // 'actual' | 'admin' | 'reviewer' | 'viewer'
    
    // Data caches
    dashboardData: null,
    waterbodiesGeoJson: null,
    alertsData: [],
    usersData: [],
    userCounts: { total: 0, admin: 0, reviewer: 0, viewer: 0 },
    auditLogs: [],
    
    // Active filters
    wbFilters: { search: '', zone: 'All', status: 'All' },
    alertFilters: { search: '', severity: 'All', status: 'All', zone: 'All', sort: 'date_desc' },
    
    // Staged Import File
    stagedFile: null,

    // Map state
    mapZoom: 1.0,
    mapPan: { x: 0, y: 0 },
    mapSelectedRecord: null,
    mapShowAlerts: true,
    mapShowPolygons: true
  };

  // DOM Elements
  const el = {
    // Shell
    sidebar: document.querySelector('.sidebar'),
    sidebarToggleBtn: document.getElementById('sidebarToggleBtn'),
    navAlertsBadge: document.getElementById('navAlertsBadge'),
    sidebarUserAvatar: document.getElementById('sidebarUserAvatar'),
    sidebarUserName: document.getElementById('sidebarUserName'),
    sidebarUserDesignation: document.getElementById('sidebarUserDesignation'),
    topbarAccountName: document.getElementById('topbarAccountName'),
    topbarRoleBadge: document.getElementById('topbarRoleBadge'),
    breadcrumbCurrent: document.getElementById('breadcrumbCurrent'),
    roleSimulatorSelect: document.getElementById('roleSimulatorSelect'),
    btnSignout: document.getElementById('btnSignout'),
    btnOpenAccountModal: document.getElementById('btnOpenAccountModal'),
    toastContainer: document.getElementById('toastContainer'),

    // Navigation links
    navLinks: {
      dashboard: document.getElementById('navDashboard'),
      waterbodies: document.getElementById('navWaterBodies'),
      alerts: document.getElementById('navAlerts'),
      map: document.getElementById('navMap'),
      import: document.getElementById('navImport'),
      reports: document.getElementById('navReports'),
      admin: document.getElementById('navAdmin')
    },

    // Sections
    sections: {
      dashboard: document.getElementById('secDashboard'),
      waterbodies: document.getElementById('secWaterBodies'),
      alerts: document.getElementById('secAlerts'),
      map: document.getElementById('secMap'),
      import: document.getElementById('secImport'),
      reports: document.getElementById('secReports'),
      admin: document.getElementById('secAdmin')
    },

    // Dashboard
    kpiWaterBodies: document.getElementById('kpiWaterBodies'),
    kpiArea: document.getElementById('kpiArea'),
    kpiActiveAlerts: document.getElementById('kpiActiveAlerts'),
    kpiAreasReview: document.getElementById('kpiAreasReview'),
    dashPriorityAlertsBody: document.getElementById('dashPriorityAlertsBody'),
    dashActivityFeed: document.getElementById('dashActivityFeed'),
    dashZoneList: document.getElementById('dashZoneList'),

    // Water Bodies
    wbSearchInput: document.getElementById('wbSearchInput'),
    wbZoneFilter: document.getElementById('wbZoneFilter'),
    wbStatusFilter: document.getElementById('wbStatusFilter'),
    wbTableBody: document.getElementById('wbTableBody'),
    wbTableState: document.getElementById('wbTableState'),
    wbCountPill: document.getElementById('wbCountPill'),

    // Alerts
    alertSearchInput: document.getElementById('alertSearchInput'),
    alertSeverityFilter: document.getElementById('alertSeverityFilter'),
    alertStatusFilter: document.getElementById('alertStatusFilter'),
    alertZoneFilter: document.getElementById('alertZoneFilter'),
    alertSortSelect: document.getElementById('alertSortSelect'),
    alertsContainer: document.getElementById('alertsContainer'),
    alertsCountPill: document.getElementById('alertsCountPill'),

    // Map
    mapCanvas: document.getElementById('mapCanvas'),
    mapWaterbodySelect: document.getElementById('mapWaterbodySelect'),
    btnMapZoomIn: document.getElementById('btnMapZoomIn'),
    btnMapZoomOut: document.getElementById('btnMapZoomOut'),
    btnMapReset: document.getElementById('btnMapReset'),
    mapToggleAlerts: document.getElementById('mapToggleAlerts'),
    mapTogglePolygons: document.getElementById('mapTogglePolygons'),

    // Import
    dropzone: document.getElementById('spatialDropzone'),
    fileInput: document.getElementById('spatialFileInput'),
    btnSampleGeojson: document.getElementById('btnSampleGeojson'),
    btnSampleCsv: document.getElementById('btnSampleCsv'),
    ingestPreviewContainer: document.getElementById('ingestPreviewContainer'),

    // Reports
    btnExportGeojson: document.getElementById('btnExportGeojson'),
    btnExportWbCsv: document.getElementById('btnExportWbCsv'),
    btnExportAlertsCsv: document.getElementById('btnExportAlertsCsv'),
    btnExportPdf: document.getElementById('btnExportPdf'),
    reportZoneSelect: document.getElementById('reportZoneSelect'),
    reportCycleSelect: document.getElementById('reportCycleSelect'),

    // Admin
    statTotal: document.getElementById('statTotal'),
    statAdmins: document.getElementById('statAdmins'),
    statReviewers: document.getElementById('statReviewers'),
    statViewers: document.getElementById('statViewers'),
    userSearchInput: document.getElementById('userSearchInput'),
    btnAddUser: document.getElementById('btnAddUser'),
    usersTableBody: document.getElementById('usersTableBody'),
    auditListContainer: document.getElementById('auditListContainer'),

    // Modals
    addUserModal: document.getElementById('addUserModal'),
    addUserForm: document.getElementById('addUserForm'),
    btnCancelAddUser: document.getElementById('btnCancelAddUser'),
    btnCloseAddUser: document.getElementById('btnCloseAddUser'),

    reviewAlertModal: document.getElementById('reviewAlertModal'),
    reviewAlertForm: document.getElementById('reviewAlertForm'),
    btnCancelReviewAlert: document.getElementById('btnCancelReviewAlert'),
    btnCloseReviewAlert: document.getElementById('btnCloseReviewAlert'),

    recordDetailModal: document.getElementById('recordDetailModal'),
    btnCloseRecordDetail: document.getElementById('btnCloseRecordDetail'),

    switchAccountModal: document.getElementById('switchAccountModal'),
    btnCloseAccountModal: document.getElementById('btnCloseAccountModal'),
    switchUserSelect: document.getElementById('switchUserSelect'),
    btnSubmitSwitchUser: document.getElementById('btnSubmitSwitchUser')
  };

  // Toast Notification Helper
  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let iconSvg = '';
    if (type === 'success') {
      iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>`;
    } else if (type === 'error') {
      iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`;
    } else {
      iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`;
    }

    toast.innerHTML = `
      <div style="flex-shrink:0;">${iconSvg}</div>
      <div style="flex:1;">${escapeHtml(message)}</div>
    `;

    el.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4500);
  }

  function getEffectiveRole() {
    if (state.simulatedRole !== 'actual') {
      return state.simulatedRole;
    }
    return state.currentUser ? state.currentUser.role : 'viewer';
  }

  function getInitials(name) {
    if (!name) return 'NW';
    const parts = name.trim().split(' ');
    if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function formatBytes(bytes, decimals = 1) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  }

  // Section Navigation Router
  function navigateTo(sectionKey) {
    if (!el.sections[sectionKey]) sectionKey = 'dashboard';
    state.currentSection = sectionKey;

    // Update active section tab
    Object.keys(el.sections).forEach(key => {
      if (el.sections[key]) {
        el.sections[key].classList.toggle('active-section', key === sectionKey);
      }
    });

    // Update active nav link
    Object.keys(el.navLinks).forEach(key => {
      if (el.navLinks[key]) {
        el.navLinks[key].classList.toggle('active', key === sectionKey);
      }
    });

    // Update breadcrumb
    const titles = {
      dashboard: 'Surveillance Dashboard',
      waterbodies: 'Water Bodies Inventory',
      alerts: 'Change Surveillance Alerts',
      map: 'GIS Spatial Map View',
      import: 'Spatial Data Ingestion',
      reports: 'Cadastral Reports & Exports',
      admin: 'Workspace Administration'
    };
    el.breadcrumbCurrent.textContent = titles[sectionKey] || 'Surveillance Workspace';

    // On mobile, close sidebar on navigation
    el.sidebar.classList.remove('open');

    // Section-specific refresh
    if (sectionKey === 'dashboard') loadDashboard();
    if (sectionKey === 'waterbodies') loadWaterbodies();
    if (sectionKey === 'alerts') loadAlerts();
    if (sectionKey === 'map') renderMap();
    if (sectionKey === 'admin') loadUsers();
  }

  // Initialize Application
  async function init() {
    setupEventListeners();
    await loadSession();
    
    // Parse initial URL hash
    const hash = window.location.hash.replace('#', '') || 'dashboard';
    navigateTo(hash);

    // Initial load of alerts count for badge
    loadAlertsCount();
  }

  // Session & Authentication
  async function loadSession() {
    try {
      const res = await window.NeerWatchAPI.getMe();
      if (res.authenticated && res.user) {
        state.currentUser = res.user;
      } else {
        // Fallback default session check: try logging in with admin seed
        try {
          const loginRes = await window.NeerWatchAPI.login('k.ramanathan@cma.tn.gov.in', 'Admin@password123');
          state.currentUser = loginRes.user;
        } catch (e) {
          state.currentUser = {
            id: 1,
            full_name: 'Dr. K. Ramanathan',
            email: 'k.ramanathan@cma.tn.gov.in',
            role: 'admin',
            designation: 'Principal Geospatial Director'
          };
        }
      }
    } catch (err) {
      console.warn('Session verification note:', err);
    }
    updateUserShellUI();
  }

  function updateUserShellUI() {
    const user = state.currentUser;
    const effectiveRole = getEffectiveRole();

    if (user) {
      el.sidebarUserName.textContent = user.full_name;
      el.sidebarUserDesignation.textContent = user.designation || 'Workspace Member';
      el.sidebarUserAvatar.textContent = getInitials(user.full_name);
      el.topbarAccountName.textContent = user.full_name;
    }

    el.topbarRoleBadge.textContent = effectiveRole.toUpperCase();
    el.topbarRoleBadge.className = `role-badge role-${effectiveRole}`;

    // Admin-only controls visibility
    if (effectiveRole === 'admin') {
      if (el.btnAddUser) el.btnAddUser.style.display = 'inline-flex';
    } else {
      if (el.btnAddUser) el.btnAddUser.style.display = 'none';
    }
  }

  // =========================================================================
  // Section 1: Dashboard
  // =========================================================================
  async function loadDashboard() {
    try {
      const data = await window.NeerWatchAPI.getDashboard();
      state.dashboardData = data;

      // Update KPI Tiles
      el.kpiWaterBodies.textContent = data.total_waterbodies;
      el.kpiArea.textContent = data.total_area_hectares.toLocaleString() + ' ha';
      el.kpiActiveAlerts.textContent = data.active_alerts_count;
      el.kpiAreasReview.textContent = data.areas_under_review;

      // Update alerts badge in sidebar
      if (el.navAlertsBadge) {
        el.navAlertsBadge.textContent = data.active_alerts_count;
      }

      // Priority Alerts
      renderDashboardPriorityAlerts();

      // Recent Activity Feed
      renderDashboardActivity(data.recent_activity || []);

      // Zone Distribution
      renderDashboardZoneList(data.zone_distribution || []);
    } catch (err) {
      console.error('Error loading dashboard data:', err);
      showToast('Could not refresh dashboard metrics', 'error');
    }
  }

  async function renderDashboardPriorityAlerts() {
    try {
      const res = await window.NeerWatchAPI.getAlerts({ status: 'Open Review', sort: 'severity_desc' });
      const alerts = (res.alerts || []).slice(0, 5);

      if (alerts.length === 0) {
        el.dashPriorityAlertsBody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding: 20px; color: var(--text-muted);">No open priority alerts at this time. All monitored water bodies are nominal.</td></tr>`;
        return;
      }

      el.dashPriorityAlertsBody.innerHTML = alerts.map(a => `
        <tr>
          <td><span class="font-mono" style="font-weight: 600;">${escapeHtml(a.record_id)}</span></td>
          <td><strong>${escapeHtml(a.waterbody_name)}</strong></td>
          <td><span class="severity-pill sev-${a.severity.toLowerCase()}">${escapeHtml(a.severity)}</span></td>
          <td>${escapeHtml(a.alert_type)}</td>
          <td>
            <button class="btn-primary btn-sm" onclick="window.NeerWatchOpenAlertReview('${a.id}')">
              Review Alert
            </button>
          </td>
        </tr>
      `).join('');
    } catch (err) {
      console.warn('Priority alerts render error:', err);
    }
  }

  function renderDashboardActivity(activities) {
    if (activities.length === 0) {
      el.dashActivityFeed.innerHTML = `<div style="padding: 16px; text-align: center; color: var(--text-muted);">No recent workspace activity recorded.</div>`;
      return;
    }

    el.dashActivityFeed.innerHTML = activities.map(act => {
      const isReview = act.type === 'REVIEW';
      const badgeClass = isReview ? 'role-reviewer' : 'role-admin';
      return `
        <div class="activity-feed-item">
          <div>
            <div style="font-weight: 600; font-size: 12px; display: flex; align-items: center; gap: 6px;">
              <span class="role-badge ${badgeClass}" style="font-size: 9.5px; padding: 1px 5px;">${act.type}</span>
              <span>${escapeHtml(act.title)}</span>
            </div>
            <div style="font-size: 11.5px; color: var(--text-secondary); margin-top: 2px;">
              ${escapeHtml(act.details)}
            </div>
            <div style="font-size: 10.5px; color: var(--text-muted); margin-top: 2px;">
              By: <span class="font-mono">${escapeHtml(act.actor)}</span>
            </div>
          </div>
          <div class="date-mono">${escapeHtml(act.timestamp)}</div>
        </div>
      `;
    }).join('');
  }

  function renderDashboardZoneList(zones) {
    if (zones.length === 0) {
      el.dashZoneList.innerHTML = `<div style="padding: 12px; color: var(--text-muted);">No zonal records found.</div>`;
      return;
    }

    el.dashZoneList.innerHTML = zones.map(z => `
      <div style="padding: 9px 0; border-bottom: 1px solid var(--border-subtle); display: flex; align-items: center; justify-content: space-between;">
        <div>
          <div style="font-weight: 700; font-size: 12px;">${escapeHtml(z.zone)}</div>
          <div style="font-size: 11px; color: var(--text-muted);">${z.count} Water Bodies</div>
        </div>
        <div class="font-mono" style="font-weight: 700; color: var(--primary-teal-dark);">
          ${z.total_area.toLocaleString()} ha
        </div>
      </div>
    `).join('');
  }

  // =========================================================================
  // Section 2: Water Bodies Inventory
  // =========================================================================
  async function loadWaterbodies() {
    el.wbTableState.style.display = 'block';
    el.wbTableState.innerHTML = `<div class="table-state-box"><div class="status-pulse" style="margin: 0 auto 10px; width: 10px; height: 10px;"></div><div>Loading Water Bodies Inventory...</div></div>`;
    el.wbTableBody.innerHTML = '';

    try {
      const res = await window.NeerWatchAPI.getWaterbodies(state.wbFilters);
      state.waterbodiesGeoJson = res;
      renderWaterbodiesTable(res.features || []);
      populateZoneDropdowns(res.features || []);
    } catch (err) {
      el.wbTableState.innerHTML = `<div class="table-state-box" style="color: var(--status-danger);">Failed to query water bodies from backend datastore.</div>`;
    }
  }

  function populateZoneDropdowns(features) {
    const zones = new Set();
    features.forEach(f => {
      if (f.properties && f.properties.zone) zones.add(f.properties.zone);
    });

    const optionsHtml = '<option value="All">All CMA Zones</option>' + 
      Array.from(zones).sort().map(z => `<option value="${escapeHtml(z)}">${escapeHtml(z)}</option>`).join('');

    if (el.wbZoneFilter && el.wbZoneFilter.options.length <= 1) {
      el.wbZoneFilter.innerHTML = optionsHtml;
    }
    if (el.alertZoneFilter && el.alertZoneFilter.options.length <= 1) {
      el.alertZoneFilter.innerHTML = optionsHtml;
    }
    if (el.reportZoneSelect && el.reportZoneSelect.options.length <= 1) {
      el.reportZoneSelect.innerHTML = optionsHtml;
    }
  }

  function renderWaterbodiesTable(features) {
    if (features.length === 0) {
      el.wbTableState.style.display = 'block';
      el.wbTableState.innerHTML = `<div class="table-state-box"><div>No water body records matched your active filters.</div></div>`;
      el.wbCountPill.textContent = '0 Records';
      return;
    }

    el.wbTableState.style.display = 'none';
    el.wbCountPill.textContent = `${features.length} Records`;

    el.wbTableBody.innerHTML = features.map(feat => {
      const p = feat.properties;
      const hasAlert = p.active_alerts_count > 0;
      const statusClass = hasAlert ? 'status-review' : 'status-monitored';
      const statusLabel = hasAlert ? `Under Review (${p.active_alerts_count} Alert)` : 'Monitored';

      return `
        <tr>
          <td><span class="font-mono" style="font-weight: 700;">${escapeHtml(p.record_id)}</span></td>
          <td>
            <strong>${escapeHtml(p.waterbody_name)}</strong>
          </td>
          <td>${escapeHtml(p.zone)}</td>
          <td><span class="font-mono">${Number(p.area_hectares).toLocaleString()}</span></td>
          <td><span class="font-mono" style="font-size: 11px; color: var(--text-muted);">${escapeHtml(p.crs || 'EPSG:4326')}</span></td>
          <td>
            <span class="status-pill ${statusClass}">${statusLabel}</span>
          </td>
          <td>
            <div style="display: flex; gap: 6px;">
              <button class="btn-secondary btn-sm" onclick="window.NeerWatchOpenRecordDetail('${escapeHtml(p.record_id)}')">
                Details
              </button>
              <button class="btn-secondary btn-sm" onclick="window.NeerWatchLocateOnMap('${escapeHtml(p.record_id)}')">
                Map
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');
  }

  // Water Body Record Detail Drawer
  window.NeerWatchOpenRecordDetail = async function(recordId) {
    try {
      const data = await window.NeerWatchAPI.getWaterbodyDetail(recordId);
      const detailContainer = document.getElementById('recordDetailBody');

      let geomInfo = 'Unknown geometry';
      let coordsCount = 0;
      if (data.geometry) {
        geomInfo = data.geometry.type;
        if (data.geometry.coordinates && data.geometry.coordinates[0]) {
          coordsCount = data.geometry.coordinates[0].length;
        }
      }

      detailContainer.innerHTML = `
        <div style="margin-bottom: 16px;">
          <h4 style="font-size: 18px; color: var(--primary-teal-dark);">${escapeHtml(data.waterbody_name)}</h4>
          <div style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">
            Cadastral Record ID: <span class="font-mono" style="font-weight: 700; color: var(--text-primary);">${escapeHtml(data.record_id)}</span>
          </div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 20px;">
          <div class="stat-card">
            <span class="stat-label">Cadastral Zone</span>
            <span style="font-weight: 700; font-size: 14px; margin-top: 2px;">${escapeHtml(data.zone)}</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">Extent Area</span>
            <span class="font-mono" style="font-weight: 700; font-size: 14px; margin-top: 2px;">${data.area_hectares} ha (${(data.area_hectares * 2.471).toFixed(1)} acres)</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">Spatial Reference</span>
            <span class="font-mono" style="font-weight: 700; font-size: 14px; margin-top: 2px;">${escapeHtml(data.crs)}</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">Geometry Type</span>
            <span style="font-weight: 700; font-size: 14px; margin-top: 2px;">${geomInfo} (${coordsCount} vertices)</span>
          </div>
        </div>

        <h5 style="margin-bottom: 8px; color: var(--primary-teal-dark);">Active Satellite Change Alerts (${(data.alerts || []).length})</h5>
        ${(data.alerts && data.alerts.length > 0) ? `
          <div style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 20px;">
            ${data.alerts.map(a => `
              <div style="border: 1px solid var(--border-color); border-radius: 4px; padding: 10px; background: #FAFEFD;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                  <span style="font-weight: 700; font-size: 12px;">${escapeHtml(a.alert_type)}</span>
                  <span class="severity-pill sev-${a.severity.toLowerCase()}">${escapeHtml(a.severity)}</span>
                </div>
                <div style="font-size: 11.5px; color: var(--text-secondary);">${escapeHtml(a.details)}</div>
                <div style="font-size: 10.5px; color: var(--text-muted); margin-top: 4px; display: flex; justify-content: space-between;">
                  <span>Status: <strong>${escapeHtml(a.status)}</strong></span>
                  <span>Detected: <span class="font-mono">${escapeHtml(a.detected_at)}</span></span>
                </div>
              </div>
            `).join('')}
          </div>
        ` : `
          <div style="padding: 10px; background: var(--bg-surface-tint); border: 1px solid var(--border-subtle); border-radius: 4px; font-size: 12px; margin-bottom: 20px;">
            No active change alerts recorded. Water body baseline boundary is currently nominal.
          </div>
        `}

        <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 20px;">
          <button class="btn-primary" onclick="window.NeerWatchLocateOnMap('${escapeHtml(data.record_id)}'); document.getElementById('recordDetailModal').classList.remove('active');">
            View on GIS Map
          </button>
        </div>
      `;

      el.recordDetailModal.classList.add('active');
    } catch (err) {
      showToast('Could not load water body record details', 'error');
    }
  };

  window.NeerWatchLocateOnMap = function(recordId) {
    navigateTo('map');
    if (el.mapWaterbodySelect) {
      el.mapWaterbodySelect.value = recordId;
    }
    state.mapSelectedRecord = recordId;
    renderMap();
    showToast(`Focused on cadastral record: ${recordId}`, 'info');
  };

  // =========================================================================
  // Section 3: Change Alerts
  // =========================================================================
  async function loadAlerts() {
    try {
      const res = await window.NeerWatchAPI.getAlerts(state.alertFilters);
      state.alertsData = res.alerts || [];
      renderAlertsList(state.alertsData);
      el.alertsCountPill.textContent = `${res.total_matched || 0} Alerts`;
    } catch (err) {
      showToast('Could not load change alerts list', 'error');
    }
  }

  function renderAlertsList(alerts) {
    if (alerts.length === 0) {
      el.alertsContainer.innerHTML = `<div style="grid-column: 1 / -1; padding: 40px; text-align: center; color: var(--text-muted); background: #FFF; border: 1px solid var(--border-color); border-radius: 4px;">No change surveillance alerts match your active filter criteria.</div>`;
      return;
    }

    const effectiveRole = getEffectiveRole();
    const canReview = effectiveRole === 'admin' || effectiveRole === 'reviewer';

    el.alertsContainer.innerHTML = alerts.map(a => `
      <div class="alert-card">
        <div class="alert-card-header">
          <div>
            <div class="alert-card-lake">${escapeHtml(a.waterbody_name)} (${escapeHtml(a.record_id)})</div>
            <div class="alert-card-title">${escapeHtml(a.alert_type)}</div>
          </div>
          <span class="severity-pill sev-${a.severity.toLowerCase()}">${escapeHtml(a.severity)}</span>
        </div>

        <div class="alert-card-body">
          ${escapeHtml(a.details)}
          ${a.area_change_pct ? `<div style="margin-top: 6px; font-weight: 700; color: var(--status-danger); font-size: 11.5px;">Area Change: ${a.area_change_pct}%</div>` : ''}
          ${a.review_notes ? `
            <div style="margin-top: 8px; padding: 6px 8px; background: var(--bg-surface-tint); border-left: 3px solid var(--primary-teal); border-radius: 2px; font-size: 11px;">
              <strong>Reviewer Note:</strong> ${escapeHtml(a.review_notes)}
            </div>
          ` : ''}
        </div>

        <div class="alert-card-footer">
          <div>
            Status: <span class="status-pill status-${a.status === 'Resolved' ? 'resolved' : 'review'}">${escapeHtml(a.status)}</span>
          </div>
          <div class="date-mono">
            ${escapeHtml(a.detected_at)}
          </div>
        </div>

        <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 6px;">
          <button class="btn-primary btn-sm" onclick="window.NeerWatchOpenAlertReview('${a.id}')">
            ${canReview ? 'Review & Update Status' : 'Inspect Details'}
          </button>
        </div>
      </div>
    `).join('');
  }

  // Review Alert Modal Controller
  window.NeerWatchOpenAlertReview = async function(alertId) {
    try {
      const data = await window.NeerWatchAPI.getAlertDetail(alertId);
      const effectiveRole = getEffectiveRole();
      const canReview = effectiveRole === 'admin' || effectiveRole === 'reviewer';

      document.getElementById('reviewAlertId').value = data.id;
      document.getElementById('reviewAlertTitle').textContent = `Review Alert: ${data.waterbody_name} (${data.alert_type})`;
      
      const summaryDiv = document.getElementById('reviewAlertSummary');
      summaryDiv.innerHTML = `
        <div style="padding: 10px; background: var(--bg-surface-tint); border: 1px solid var(--border-color); border-radius: 4px; margin-bottom: 12px; font-size: 12px;">
          <div><strong>Alert Type:</strong> ${escapeHtml(data.alert_type)} | <strong>Severity:</strong> <span class="severity-pill sev-${data.severity.toLowerCase()}">${data.severity}</span></div>
          <div style="margin-top: 4px;"><strong>Satellite Finding:</strong> ${escapeHtml(data.details)}</div>
          <div style="margin-top: 4px; color: var(--text-muted); font-size: 11px;">Detected: <span class="font-mono">${escapeHtml(data.detected_at)}</span> | Monitoring Cycle: <span class="font-mono">${escapeHtml(data.cycle)}</span></div>
        </div>
      `;

      // Form inputs
      const statusSelect = document.getElementById('reviewAlertStatus');
      const notesText = document.getElementById('reviewAlertNotes');
      const submitBtn = el.reviewAlertForm.querySelector('button[type="submit"]');

      statusSelect.value = data.status;
      notesText.value = data.review_notes || '';

      if (!canReview) {
        statusSelect.disabled = true;
        notesText.disabled = true;
        submitBtn.style.display = 'none';
        document.getElementById('reviewRoleNotice').style.display = 'block';
        document.getElementById('reviewRoleNotice').textContent = 'Viewer Role Active: Read-only access. You can view previous review notes but cannot modify alert statuses.';
      } else {
        statusSelect.disabled = false;
        notesText.disabled = false;
        submitBtn.style.display = 'inline-flex';
        document.getElementById('reviewRoleNotice').style.display = 'none';
      }

      // History Timeline
      const histDiv = document.getElementById('reviewAlertHistory');
      if (data.reviews_history && data.reviews_history.length > 0) {
        histDiv.innerHTML = `
          <h5 style="margin-top: 14px; margin-bottom: 6px; font-size: 12px; color: var(--primary-teal-dark);">Review Audit Trail (${data.reviews_history.length})</h5>
          <div style="max-height: 140px; overflow-y: auto; border: 1px solid var(--border-subtle); border-radius: 4px; padding: 6px;">
            ${data.reviews_history.map(rh => `
              <div style="padding: 6px 0; border-bottom: 1px solid var(--border-subtle); font-size: 11px;">
                <div style="display: flex; justify-content: space-between;">
                  <strong>${escapeHtml(rh.reviewer_name)}</strong>
                  <span class="date-mono">${escapeHtml(rh.reviewed_at)}</span>
                </div>
                <div style="color: var(--primary-teal); font-weight: 600;">Status updated: ${escapeHtml(rh.previous_status)} &rarr; ${escapeHtml(rh.new_status)}</div>
                <div style="color: var(--text-secondary); margin-top: 2px;">${escapeHtml(rh.notes)}</div>
              </div>
            `).join('')}
          </div>
        `;
      } else {
        histDiv.innerHTML = `<div style="font-size: 11px; color: var(--text-muted); margin-top: 10px;">No previous reviews recorded for this alert yet.</div>`;
      }

      el.reviewAlertModal.classList.add('active');
    } catch (err) {
      showToast('Could not open alert review drawer', 'error');
    }
  };

  async function loadAlertsCount() {
    try {
      const res = await window.NeerWatchAPI.getAlerts();
      if (el.navAlertsBadge) {
        el.navAlertsBadge.textContent = res.active_count || 0;
      }
    } catch (e) {}
  }

  // =========================================================================
  // Section 4: GIS Spatial Map Viewer
  // =========================================================================
  async function renderMap() {
    const canvas = el.mapCanvas;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas dimensions to viewport
    canvas.width = canvas.parentElement.clientWidth;
    canvas.height = canvas.parentElement.clientHeight;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Fetch water bodies if not already loaded
    if (!state.waterbodiesGeoJson) {
      try {
        state.waterbodiesGeoJson = await window.NeerWatchAPI.getWaterbodies();
      } catch (err) {
        ctx.fillStyle = '#666';
        ctx.font = '14px sans-serif';
        ctx.fillText('Could not load spatial geometries for Chennai map.', 40, 60);
        return;
      }
    }

    const features = state.waterbodiesGeoJson.features || [];

    // Populate lake jump dropdown
    if (el.mapWaterbodySelect && el.mapWaterbodySelect.options.length <= 1) {
      el.mapWaterbodySelect.innerHTML = '<option value="">All Chennai Water Bodies</option>' +
        features.map(f => `<option value="${escapeHtml(f.properties.record_id)}">${escapeHtml(f.properties.waterbody_name)}</option>`).join('');
    }

    // Chennai Geographical Bounding Box
    // Lon: ~80.00 to 80.26, Lat: ~12.88 to 13.20
    const bounds = { minLon: 80.00, maxLon: 80.26, minLat: 12.88, maxLat: 13.20 };

    // Projection helper: Lon/Lat -> Canvas (x, y)
    function project(lon, lat) {
      const normX = (lon - bounds.minLon) / (bounds.maxLon - bounds.minLon);
      const normY = 1.0 - (lat - bounds.minLat) / (bounds.maxLat - bounds.minLat);

      const margin = 50;
      const w = canvas.width - margin * 2;
      const h = canvas.height - margin * 2;

      const baseX = margin + normX * w;
      const baseY = margin + normY * h;

      // Apply pan and zoom
      const centerX = canvas.width / 2;
      const centerY = canvas.height / 2;

      const x = centerX + (baseX - centerX + state.mapPan.x) * state.mapZoom;
      const y = centerY + (baseY - centerY + state.mapPan.y) * state.mapZoom;

      return { x, y };
    }

    // Background Grid
    ctx.strokeStyle = '#D4E8E3';
    ctx.lineWidth = 1;
    for (let x = 0; x < canvas.width; x += 40) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, canvas.height);
      ctx.stroke();
    }
    for (let y = 0; y < canvas.height; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvas.width, y);
      ctx.stroke();
    }

    // Draw Water Bodies Polygons
    if (state.mapShowPolygons) {
      features.forEach(feat => {
        const geom = feat.geometry;
        const p = feat.properties;
        const isSelected = state.mapSelectedRecord === p.record_id;
        const hasAlert = p.active_alerts_count > 0;

        if (!geom) return;

        let rings = [];
        if (geom.type === 'Polygon') {
          rings = geom.coordinates;
        } else if (geom.type === 'MultiPolygon') {
          rings = geom.coordinates.flat(1);
        }

        rings.forEach(ring => {
          if (!ring || ring.length === 0) return;
          ctx.beginPath();
          ring.forEach((coord, i) => {
            const pt = project(coord[0], coord[1]);
            if (i === 0) ctx.moveTo(pt.x, pt.y);
            else ctx.lineTo(pt.x, pt.y);
          });
          ctx.closePath();

          // Style polygon
          if (isSelected) {
            ctx.fillStyle = 'rgba(20, 114, 109, 0.55)';
            ctx.strokeStyle = '#004340';
            ctx.lineWidth = 3;
          } else if (hasAlert) {
            ctx.fillStyle = 'rgba(230, 140, 40, 0.35)';
            ctx.strokeStyle = '#B86A14';
            ctx.lineWidth = 2;
          } else {
            ctx.fillStyle = 'rgba(40, 160, 145, 0.30)';
            ctx.strokeStyle = '#0D5C58';
            ctx.lineWidth = 1.5;
          }
          ctx.fill();
          ctx.stroke();

          // Lake Name Label
          const firstPt = project(ring[0][0], ring[0][1]);
          ctx.fillStyle = '#0E1E1C';
          ctx.font = 'bold 11px sans-serif';
          ctx.fillText(p.waterbody_name, firstPt.x + 4, firstPt.y - 4);
        });
      });
    }

    // Draw Alert Markers
    if (state.mapShowAlerts && state.alertsData) {
      state.alertsData.forEach(alert => {
        // Find matching water body feature
        const match = features.find(f => f.properties.record_id === alert.record_id);
        if (match && match.geometry && match.geometry.coordinates) {
          let coords = null;
          if (match.geometry.type === 'Polygon') {
            coords = match.geometry.coordinates[0][0];
          } else if (match.geometry.type === 'Point') {
            coords = match.geometry.coordinates;
          }
          if (coords) {
            const pt = project(coords[0], coords[1]);

            // Draw Alert Pin
            const isHigh = alert.severity === 'High';
            ctx.beginPath();
            ctx.arc(pt.x, pt.y, isHigh ? 7 : 5, 0, Math.PI * 2);
            ctx.fillStyle = isHigh ? '#C42B1C' : '#996500';
            ctx.fill();
            ctx.strokeStyle = '#FFFFFF';
            ctx.lineWidth = 2;
            ctx.stroke();

            // Outer pulse ring
            ctx.beginPath();
            ctx.arc(pt.x, pt.y, isHigh ? 12 : 9, 0, Math.PI * 2);
            ctx.strokeStyle = isHigh ? 'rgba(196, 43, 28, 0.4)' : 'rgba(153, 101, 0, 0.4)';
            ctx.lineWidth = 1.5;
            ctx.stroke();
          }
        }
      });
    }
  }

  // =========================================================================
  // Section 5: Spatial Data Ingestion
  // =========================================================================
  function handleSelectedFile(file) {
    if (!file) return;

    const ext = file.name.split('.').pop().toLowerCase();
    let formatHint = 'unknown';
    if (ext === 'geojson' || ext === 'json') formatHint = 'geojson';
    if (ext === 'csv') formatHint = 'csv';

    const reader = new FileReader();
    reader.onload = async (e) => {
      const content = e.target.result;
      state.stagedFile = {
        name: file.name,
        size: formatBytes(file.size),
        content,
        formatHint
      };

      try {
        showToast(`Validating spatial dataset: ${file.name}...`, 'info');
        const validation = await window.NeerWatchAPI.validateSpatial(content, file.name, formatHint);
        state.stagedFile.validation = validation;
        renderIngestPreview(state.stagedFile);
      } catch (err) {
        showToast(err.message || 'Spatial dataset validation failed', 'error');
      }
    };
    reader.readAsText(file);
  }

  function renderIngestPreview(staged) {
    const v = staged.validation;
    const effectiveRole = getEffectiveRole();
    const canCommit = v.valid && (effectiveRole === 'admin' || effectiveRole === 'reviewer');

    el.ingestPreviewContainer.innerHTML = `
      <div class="ingest-preview-card" style="margin-top: 14px; border: 1px solid var(--border-color); border-radius: 4px; background: #FFF;">
        <div class="preview-header" style="padding: 10px 14px; background: var(--bg-surface-tint); border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center;">
          <div style="font-weight: 700; font-size: 13px;">
            ${escapeHtml(staged.name)} <span class="font-mono" style="font-size: 11px; color: var(--text-muted);">(${staged.size})</span>
          </div>
          <div>
            <span class="panel-badge">${v.valid_count} Records Valid</span>
            <span class="panel-badge" style="color: ${v.crs_supported ? 'var(--status-success)' : 'var(--status-danger)'};">
              ${escapeHtml(v.detected_crs)}
            </span>
          </div>
        </div>
        <div style="padding: 14px;">
          <div style="display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; font-size: 12px;">
            <div style="color: ${v.crs_supported ? 'var(--status-success)' : 'var(--status-danger)'};">
              ${v.crs_supported ? '&#10003; Standard Geographic CRS: WGS 84 (EPSG:4326)' : '&#10007; Non-standard CRS: requires WGS 84. Coordinates are not silently distorted.'}
            </div>
            <div style="color: ${v.error_count === 0 ? 'var(--status-success)' : 'var(--status-danger)'};">
              ${v.error_count === 0 ? '&#10003; Geometry Schema: valid polygons and coordinate attributes' : `&#10007; ${v.error_count} schema/geometry errors identified`}
            </div>
            <div style="color: var(--status-success);">
              &#10003; Property Aliases: record_id, waterbody_name, zone, area_hectares, geometry mapped
            </div>
          </div>

          ${v.errors && v.errors.length > 0 ? `
            <div style="background: var(--status-danger-bg); border: 1px solid var(--status-danger-border); border-radius: 4px; padding: 8px 10px; margin-bottom: 12px; font-size: 11.5px; color: var(--status-danger);">
              <strong>Errors detected:</strong>
              <ul style="margin: 4px 0 0 16px;">
                ${v.errors.map(e => `<li>${escapeHtml(e)}</li>`).join('')}
              </ul>
            </div>
          ` : ''}

          ${v.sample_records && v.sample_records.length > 0 ? `
            <div style="font-size: 11px; font-weight: 700; color: var(--text-secondary); text-transform: uppercase; margin-bottom: 4px;">Pre-commit Record Preview</div>
            <div class="table-wrapper" style="max-height: 140px; margin-bottom: 14px;">
              <table class="cma-table" style="font-size: 11px;">
                <thead>
                  <tr>
                    <th>Record ID</th>
                    <th>Water Body</th>
                    <th>Zone</th>
                    <th>Area (ha)</th>
                  </tr>
                </thead>
                <tbody>
                  ${v.sample_records.map(r => `
                    <tr>
                      <td class="font-mono">${escapeHtml(r.record_id)}</td>
                      <td>${escapeHtml(r.waterbody_name)}</td>
                      <td>${escapeHtml(r.zone)}</td>
                      <td class="font-mono">${r.area_hectares}</td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          ` : ''}

          ${!canCommit && effectiveRole === 'viewer' ? `
            <div style="padding: 8px 10px; background: var(--status-warning-bg); border: 1px solid var(--status-warning-border); border-radius: 4px; font-size: 11.5px; margin-bottom: 10px;">
              Viewer permissions are read-only. Committing spatial cadastral updates requires Reviewer or Administrator authority.
            </div>
          ` : ''}

          <div style="display: flex; justify-content: flex-end; gap: 10px;">
            <button class="btn-secondary" id="btnCancelIngest">Cancel</button>
            <button class="btn-primary" id="btnCommitSpatial" ${canCommit ? '' : 'disabled'}>
              Confirm &amp; Commit to Cadastre
            </button>
          </div>
        </div>
      </div>
    `;

    document.getElementById('btnCancelIngest').addEventListener('click', () => {
      state.stagedFile = null;
      el.ingestPreviewContainer.innerHTML = '';
      el.fileInput.value = '';
    });

    const commitBtn = document.getElementById('btnCommitSpatial');
    if (commitBtn) {
      commitBtn.addEventListener('click', async () => {
        if (!state.stagedFile || !state.stagedFile.validation) return;
        commitBtn.disabled = true;
        commitBtn.textContent = 'Committing to SQLite...';

        try {
          const records = state.stagedFile.validation.records;
          const crs = state.stagedFile.validation.detected_crs;
          const res = await window.NeerWatchAPI.commitSpatial(records, crs);
          
          showToast(res.message || 'Spatial dataset successfully committed!', 'success');
          state.stagedFile = null;
          el.ingestPreviewContainer.innerHTML = '';
          el.fileInput.value = '';

          // Refresh water bodies & map cache
          state.waterbodiesGeoJson = null;
          loadDashboard();
        } catch (err) {
          showToast(err.message || 'Failed to commit dataset to workspace', 'error');
          commitBtn.disabled = false;
          commitBtn.textContent = 'Confirm & Commit to Cadastre';
        }
      });
    }
  }

  // =========================================================================
  // Section 7: Administration
  // =========================================================================
  async function loadUsers() {
    try {
      const res = await window.NeerWatchAPI.getUsers();
      state.usersData = res.users || [];
      state.userCounts = res.counts || { total: 0, admin: 0, reviewer: 0, viewer: 0 };
      
      el.statTotal.textContent = state.userCounts.total;
      el.statAdmins.textContent = state.userCounts.admin;
      el.statReviewers.textContent = state.userCounts.reviewer;
      el.statViewers.textContent = state.userCounts.viewer;

      renderUsersTable();
      loadAuditLogs();
    } catch (err) {
      showToast('Could not load personnel directory', 'error');
    }
  }

  function renderUsersTable() {
    const q = (el.userSearchInput.value || '').trim().toLowerCase();
    const filtered = state.usersData.filter(u => {
      return (u.full_name || '').toLowerCase().includes(q) ||
             (u.email || '').toLowerCase().includes(q) ||
             (u.designation || '').toLowerCase().includes(q);
    });

    if (filtered.length === 0) {
      el.usersTableBody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 24px; color: var(--text-muted);">No personnel records match your query.</td></tr>`;
      return;
    }

    el.usersTableBody.innerHTML = filtered.map(u => `
      <tr>
        <td>
          <div style="display: flex; align-items: center; gap: 8px;">
            <div class="user-avatar" style="width: 26px; height: 26px; font-size: 10px;">${getInitials(u.full_name)}</div>
            <div>
              <div style="font-weight: 700;">${escapeHtml(u.full_name)}</div>
              <div style="font-size: 11px; color: var(--text-muted);">${escapeHtml(u.designation)}</div>
            </div>
          </div>
        </td>
        <td><span class="email-mono">${escapeHtml(u.email)}</span></td>
        <td><span class="role-badge role-${u.role}">${u.role.toUpperCase()}</span></td>
        <td><span class="date-mono">${escapeHtml(u.created_at)}</span></td>
        <td>
          <span style="font-size: 11px; font-weight: 600; color: var(--status-success); display: inline-flex; align-items: center; gap: 4px;">
            <span class="gis-dot"></span> Authorized
          </span>
        </td>
      </tr>
    `).join('');
  }

  async function loadAuditLogs() {
    try {
      const res = await window.NeerWatchAPI.getAuditLogins(12);
      state.auditLogs = res.logs || [];
      
      if (state.auditLogs.length === 0) {
        el.auditListContainer.innerHTML = `<div style="text-align:center; padding: 20px; color: var(--text-muted);">No recent authentication events recorded.</div>`;
        return;
      }

      el.auditListContainer.innerHTML = state.auditLogs.map(log => {
        const isSuccess = log.status === 'SUCCESS';
        return `
          <div style="padding: 8px 10px; border-bottom: 1px solid var(--border-subtle); display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; font-size: 11.5px;">
            <div>
              <div style="display: flex; gap: 6px; align-items: center;">
                <span class="font-mono" style="font-weight: 600;">${escapeHtml(log.email)}</span>
                <span class="panel-badge" style="font-size: 9.5px; padding: 1px 4px;">${escapeHtml(log.event_type)}</span>
                <span class="status-pill status-${isSuccess ? 'monitored' : 'review'}" style="font-size: 9.5px; padding: 1px 5px;">${isSuccess ? 'PASS' : 'FAIL'}</span>
              </div>
              <div style="color: var(--text-secondary); margin-top: 2px;">${escapeHtml(log.details)}</div>
            </div>
            <div class="date-mono">${escapeHtml(log.timestamp)}</div>
          </div>
        `;
      }).join('');
    } catch (e) {}
  }

  // =========================================================================
  // Global Event Listeners & Wire-up
  // =========================================================================
  function setupEventListeners() {
    // Navigation routing
    Object.keys(el.navLinks).forEach(key => {
      const link = el.navLinks[key];
      if (link) {
        link.addEventListener('click', (e) => {
          e.preventDefault();
          window.location.hash = key;
          navigateTo(key);
        });
      }
    });

    window.addEventListener('hashchange', () => {
      const key = window.location.hash.replace('#', '') || 'dashboard';
      navigateTo(key);
    });

    // Mobile sidebar toggle
    el.sidebarToggleBtn.addEventListener('click', () => {
      el.sidebar.classList.toggle('open');
    });

    // Role Simulator Preview Control
    el.roleSimulatorSelect.addEventListener('change', (e) => {
      state.simulatedRole = e.target.value;
      updateUserShellUI();
      if (state.currentSection === 'alerts') renderAlertsList(state.alertsData);
      if (state.currentSection === 'import' && state.stagedFile) renderIngestPreview(state.stagedFile);
      showToast(`Role simulator switched to: ${state.simulatedRole.toUpperCase()} (UI Preview Only)`, 'info');
    });

    // Sign Out
    el.btnSignout.addEventListener('click', async () => {
      if (confirm('Are you sure you want to sign out of your authenticated NeerWatch session?')) {
        await window.NeerWatchAPI.logout();
        showToast('Session terminated.', 'info');
        window.location.reload();
      }
    });

    // Switch Account Modal
    el.btnOpenAccountModal.addEventListener('click', () => {
      el.switchAccountModal.classList.add('active');
    });

    el.btnCloseAccountModal.addEventListener('click', () => {
      el.switchAccountModal.classList.remove('active');
    });

    el.btnSubmitSwitchUser.addEventListener('click', async () => {
      const sel = el.switchUserSelect.value;
      let email = '';
      let pass = '';
      if (sel === 'admin') {
        email = 'k.ramanathan@cma.tn.gov.in';
        pass = 'Admin@password123';
      } else if (sel === 'reviewer') {
        email = 's.priya@wrd.tn.gov.in';
        pass = 'Reviewer@123';
      } else if (sel === 'viewer') {
        email = 'm.arun@tndma.gov.in';
        pass = 'Viewer@123';
      }

      try {
        const res = await window.NeerWatchAPI.login(email, pass);
        state.currentUser = res.user;
        state.simulatedRole = 'actual';
        el.roleSimulatorSelect.value = 'actual';
        updateUserShellUI();
        el.switchAccountModal.classList.remove('active');
        showToast(`Authenticated as: ${res.user.full_name} (${res.user.role.toUpperCase()})`, 'success');
        navigateTo(state.currentSection);
      } catch (err) {
        showToast(err.message || 'Authentication error', 'error');
      }
    });

    // Water Bodies Filters
    el.wbSearchInput.addEventListener('input', (e) => {
      state.wbFilters.search = e.target.value;
      loadWaterbodies();
    });
    el.wbZoneFilter.addEventListener('change', (e) => {
      state.wbFilters.zone = e.target.value;
      loadWaterbodies();
    });
    el.wbStatusFilter.addEventListener('change', (e) => {
      state.wbFilters.status = e.target.value;
      loadWaterbodies();
    });

    // Alerts Filters
    el.alertSearchInput.addEventListener('input', (e) => {
      state.alertFilters.search = e.target.value;
      loadAlerts();
    });
    el.alertSeverityFilter.addEventListener('change', (e) => {
      state.alertFilters.severity = e.target.value;
      loadAlerts();
    });
    el.alertStatusFilter.addEventListener('change', (e) => {
      state.alertFilters.status = e.target.value;
      loadAlerts();
    });
    el.alertZoneFilter.addEventListener('change', (e) => {
      state.alertFilters.zone = e.target.value;
      loadAlerts();
    });
    el.alertSortSelect.addEventListener('change', (e) => {
      state.alertFilters.sort = e.target.value;
      loadAlerts();
    });

    // Alert Review Form Submit
    el.reviewAlertForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const alertId = document.getElementById('reviewAlertId').value;
      const status = document.getElementById('reviewAlertStatus').value;
      const notes = document.getElementById('reviewAlertNotes').value.trim();

      const submitBtn = el.reviewAlertForm.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      submitBtn.textContent = 'Saving Review...';

      try {
        const res = await window.NeerWatchAPI.reviewAlert(alertId, status, notes);
        showToast(res.message || 'Alert review saved successfully!', 'success');
        el.reviewAlertModal.classList.remove('active');
        loadAlerts();
        loadAlertsCount();
      } catch (err) {
        showToast(err.message || 'Could not record alert review note', 'error');
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Save Review & Update Status';
      }
    });

    el.btnCancelReviewAlert.addEventListener('click', () => el.reviewAlertModal.classList.remove('active'));
    el.btnCloseReviewAlert.addEventListener('click', () => el.reviewAlertModal.classList.remove('active'));
    el.btnCloseRecordDetail.addEventListener('click', () => el.recordDetailModal.classList.remove('active'));

    // Map Controls
    el.btnMapZoomIn.addEventListener('click', () => {
      state.mapZoom = Math.min(state.mapZoom + 0.3, 3.5);
      renderMap();
    });
    el.btnMapZoomOut.addEventListener('click', () => {
      state.mapZoom = Math.max(state.mapZoom - 0.3, 0.6);
      renderMap();
    });
    el.btnMapReset.addEventListener('click', () => {
      state.mapZoom = 1.0;
      state.mapPan = { x: 0, y: 0 };
      state.mapSelectedRecord = null;
      if (el.mapWaterbodySelect) el.mapWaterbodySelect.value = '';
      renderMap();
    });
    el.mapToggleAlerts.addEventListener('change', (e) => {
      state.mapShowAlerts = e.target.checked;
      renderMap();
    });
    el.mapTogglePolygons.addEventListener('change', (e) => {
      state.mapShowPolygons = e.target.checked;
      renderMap();
    });
    el.mapWaterbodySelect.addEventListener('change', (e) => {
      state.mapSelectedRecord = e.target.value;
      renderMap();
    });

    // Window resize redrawing map
    window.addEventListener('resize', () => {
      if (state.currentSection === 'map') renderMap();
    });

    // Spatial Drag and Drop
    el.dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      el.dropzone.classList.add('drag-over');
    });
    el.dropzone.addEventListener('dragleave', () => {
      el.dropzone.classList.remove('drag-over');
    });
    el.dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      el.dropzone.classList.remove('drag-over');
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleSelectedFile(e.dataTransfer.files[0]);
      }
    });
    el.dropzone.addEventListener('click', (e) => {
      if (e.target.closest('.sample-loaders')) return;
      el.fileInput.click();
    });
    el.fileInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleSelectedFile(e.target.files[0]);
      }
    });

    // Quick Sample File Loaders
    el.btnSampleGeojson.addEventListener('click', async (e) => {
      e.stopPropagation();
      try {
        const resp = await fetch('/samples/sample_waterbodies.geojson');
        const text = await resp.text();
        const fakeFile = new File([text], 'sample_chennai_reservoirs.geojson', { type: 'application/geo+json' });
        handleSelectedFile(fakeFile);
      } catch (err) {
        showToast('Could not load sample GeoJSON', 'error');
      }
    });

    el.btnSampleCsv.addEventListener('click', async (e) => {
      e.stopPropagation();
      try {
        const resp = await fetch('/samples/sample_waterbodies.csv');
        const text = await resp.text();
        const fakeFile = new File([text], 'sample_chennai_tanks.csv', { type: 'text/csv' });
        handleSelectedFile(fakeFile);
      } catch (err) {
        showToast('Could not load sample CSV', 'error');
      }
    });

    // Exports
    el.btnExportGeojson.addEventListener('click', () => {
      const zone = el.reportZoneSelect.value;
      const url = `/api/export/waterbodies.geojson${zone !== 'All' ? '?zone=' + encodeURIComponent(zone) : ''}`;
      window.location.href = url;
      showToast('Cadastral Water Bodies GeoJSON export started.', 'success');
    });

    el.btnExportWbCsv.addEventListener('click', () => {
      const zone = el.reportZoneSelect.value;
      const url = `/api/export/waterbodies.csv${zone !== 'All' ? '?zone=' + encodeURIComponent(zone) : ''}`;
      window.location.href = url;
      showToast('Water Bodies CSV inventory export started.', 'success');
    });

    el.btnExportAlertsCsv.addEventListener('click', () => {
      window.location.href = '/api/export/alerts.csv';
      showToast('Surveillance Change Alerts CSV export started.', 'success');
    });

    el.btnExportPdf.addEventListener('click', () => {
      window.open('/api/export/digest.pdf', '_blank');
      showToast('Opening Executive Cadastral Digest...', 'info');
    });

    // Administration Add User
    el.btnAddUser.addEventListener('click', () => {
      el.addUserForm.reset();
      el.addUserModal.classList.add('active');
    });
    el.btnCancelAddUser.addEventListener('click', () => el.addUserModal.classList.remove('active'));
    el.btnCloseAddUser.addEventListener('click', () => el.addUserModal.classList.remove('active'));

    el.addUserForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const fullName = document.getElementById('newUserName').value.trim();
      const email = document.getElementById('newUserEmail').value.trim();
      const role = document.getElementById('newUserRole').value;
      const designation = document.getElementById('newUserDesignation').value.trim();
      const password = document.getElementById('newUserPassword').value;

      if (!fullName || !email || password.length < 8) {
        showToast('Please fulfill all validation rules (min 8 chars password).', 'error');
        return;
      }

      const submitBtn = el.addUserForm.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      submitBtn.textContent = 'Provisioning...';

      try {
        const res = await window.NeerWatchAPI.createUser({
          full_name: fullName,
          email,
          role,
          designation,
          password
        });
        showToast(`User ${fullName} (${email}) provisioned!`, 'success');
        el.addUserModal.classList.remove('active');
        loadUsers();
      } catch (err) {
        showToast(err.message || 'Could not provision user account', 'error');
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Create Authorized Account';
      }
    });

    el.userSearchInput.addEventListener('input', () => renderUsersTable());
  }

  init();
});
