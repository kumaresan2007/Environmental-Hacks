/**
 * NeerWatch API Client Module
 * Provides standardized communication with the Python/SQLite backend.
 */

const API = {
  baseUrl: '/api',

  getToken() {
    return localStorage.getItem('neerwatch_token');
  },

  setToken(token) {
    if (token) {
      localStorage.setItem('neerwatch_token', token);
    } else {
      localStorage.removeItem('neerwatch_token');
    }
  },

  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const headers = {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    };

    const token = this.getToken();
    if (token) {
      headers['X-Session-Token'] = token;
      headers['Authorization'] = `Bearer ${token}`;
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers
      });

      const contentType = response.headers.get('content-type') || '';
      if (!contentType.includes('application/json')) {
        if (!response.ok) {
          throw new Error(`Server returned HTTP ${response.status}: ${response.statusText}`);
        }
        return response;
      }

      const data = await response.json();

      if (!response.ok) {
        const error = new Error(data.error || `HTTP error ${response.status}`);
        error.status = response.status;
        error.code = data.code;
        throw error;
      }

      return data;
    } catch (err) {
      console.error(`API Error on ${endpoint}:`, err);
      throw err;
    }
  },

  // Authentication
  async getMe() {
    return this.request('/auth/me');
  },

  async login(email, password) {
    const data = await this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    });
    if (data.token) {
      this.setToken(data.token);
    }
    return data;
  },

  async logout() {
    try {
      await this.request('/auth/logout', { method: 'POST' });
    } finally {
      this.setToken(null);
    }
  },

  // Dashboard Metrics
  async getDashboard() {
    return this.request('/dashboard');
  },

  // Water Bodies
  async getWaterbodies(filters = {}) {
    const params = new URLSearchParams();
    if (filters.search) params.append('search', filters.search);
    if (filters.zone && filters.zone !== 'All') params.append('zone', filters.zone);
    if (filters.status && filters.status !== 'All') params.append('status', filters.status);
    const qs = params.toString() ? `?${params.toString()}` : '';
    return this.request(`/waterbodies${qs}`);
  },

  async getWaterbodyDetail(idOrRecordId) {
    return this.request(`/waterbodies/${encodeURIComponent(idOrRecordId)}`);
  },

  // Change Alerts
  async getAlerts(filters = {}) {
    const params = new URLSearchParams();
    if (filters.search) params.append('search', filters.search);
    if (filters.severity && filters.severity !== 'All') params.append('severity', filters.severity);
    if (filters.status && filters.status !== 'All') params.append('status', filters.status);
    if (filters.zone && filters.zone !== 'All') params.append('zone', filters.zone);
    if (filters.sort) params.append('sort', filters.sort);
    const qs = params.toString() ? `?${params.toString()}` : '';
    return this.request(`/alerts${qs}`);
  },

  async getAlertDetail(idOrRecordId) {
    return this.request(`/alerts/${encodeURIComponent(idOrRecordId)}`);
  },

  async reviewAlert(idOrRecordId, status, notes) {
    return this.request(`/alerts/${encodeURIComponent(idOrRecordId)}/review`, {
      method: 'POST',
      body: JSON.stringify({ status, notes })
    });
  },

  // Personnel Directory
  async getUsers() {
    return this.request('/users');
  },

  async createUser(userData) {
    return this.request('/users', {
      method: 'POST',
      body: JSON.stringify(userData)
    });
  },

  // Audit Logs
  async getAuditLogins(limit = 20) {
    return this.request(`/audit/logins?limit=${limit}`);
  },

  // Spatial Ingestion
  async validateSpatial(content, filename, format) {
    return this.request('/spatial/validate', {
      method: 'POST',
      body: JSON.stringify({ content, filename, format })
    });
  },

  async commitSpatial(records, crs) {
    return this.request('/spatial/commit', {
      method: 'POST',
      body: JSON.stringify({ records, crs })
    });
  }
};

window.NeerWatchAPI = API;
