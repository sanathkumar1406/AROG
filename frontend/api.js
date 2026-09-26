/**
 * AROG - Central API Configuration & Client
 * Connects existing HTML/CSS frontend to FastAPI backend.
 * Provides unified authentication, access control guard, consistent navigation,
 * user profile modal, real QR generation, and geolocation assistance.
 */

const AROG_API = {
  // Base URL - dynamically detects current origin or defaults to backend port 8000
  get BASE_URL() {
    if (typeof window !== 'undefined') {
      const origin = window.location.origin;
      if (origin && (origin.includes(':8000') || origin.includes(':3000') || origin.includes('localhost') || origin.includes('127.0.0.1'))) {
        return 'http://localhost:8000';
      }
      return origin || 'http://localhost:8000';
    }
    return 'http://localhost:8000';
  },

  // ---- Auth token & user storage ----
  getToken() {
    return localStorage.getItem('arog_token');
  },
  setToken(token) {
    localStorage.setItem('arog_token', token);
  },
  clearToken() {
    localStorage.removeItem('arog_token');
  },
  getUserInfo() {
    const info = localStorage.getItem('arog_user');
    return info ? JSON.parse(info) : null;
  },
  getCurrentUser() {
    return this.getUserInfo();
  },
  setUserInfo(name, email, role = 'Travelling Clinician', id = null) {
    localStorage.setItem('arog_user', JSON.stringify({ name, full_name: name, email, role, id }));
  },
  isLoggedIn() {
    return !!this.getToken();
  },

  logout() {
    this.clearToken();
    localStorage.removeItem('arog_user');
    window.location.href = '/frontend/arog_healthcare_continuity_home/code.html';
  },

  // ---- Access Control Guard ----
  checkAuthGuard() {
    if (typeof window === 'undefined') return;
    const path = window.location.pathname;

    const isPublic =
      path.includes('arog_healthcare_continuity_home') ||
      path.includes('arog_sign_in_clinical_portal') ||
      path === '/' ||
      path.endsWith('index.html');

    if (!isPublic && !this.isLoggedIn()) {
      // User is trying to access protected area without being logged in
      console.warn('Access denied: Authentication required for clinical continuity portal.');
      window.location.replace('/frontend/arog_sign_in_clinical_portal/code.html');
    }
  },

  // ---- Core fetch wrapper with auth headers ----
  async request(endpoint, options = {}) {
    const url = `${this.BASE_URL}${endpoint}`;
    const headers = {
      ...(options.headers || {}),
    };

    // Add auth token if available
    const token = this.getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    // Add JSON content type for non-FormData bodies
    if (options.body && !(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      if (response.status === 401) {
        this.clearToken();
        const path = window.location.pathname;
        const isPublic =
          path.includes('arog_healthcare_continuity_home') ||
          path.includes('arog_sign_in_clinical_portal');
        if (!isPublic) {
          window.location.replace('/frontend/arog_sign_in_clinical_portal/code.html');
        }
      }

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || `API Error: ${response.status}`);
      }

      return data;
    } catch (error) {
      if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
        throw new Error('Cannot connect to AROG backend. Is the server running on port 8000?');
      }
      throw error;
    }
  },

  // ---- Auth APIs ----
  async login(email, password) {
    const data = await this.request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    this.setToken(data.access_token);
    this.setUserInfo(data.user_name, data.user_email);
    // Refresh full profile in background
    try {
      await this.getProfile();
    } catch (_) { }
    return data;
  },

  async signup(name, email, password) {
    const data = await this.request('/api/auth/signup', {
      method: 'POST',
      body: JSON.stringify({ name, email, password }),
    });
    this.setToken(data.access_token);
    this.setUserInfo(data.user_name, data.user_email);
    return data;
  },

  async getProfile() {
    const profile = await this.request('/api/auth/me');
    if (profile) {
      this.setUserInfo(profile.name, profile.email, profile.role || 'Travelling Clinician', profile.id);
    }
    return profile;
  },

  // ---- Patient APIs ----
  async getPatients(search = '', skip = 0, limit = 10) {
    const params = new URLSearchParams();
    if (search && search.trim()) {
      params.append('search', search.trim());
      params.append('limit', '50');
    } else {
      params.append('limit', String(limit));
    }
    if (skip > 0) params.append('skip', String(skip));

    const q = params.toString() ? `?${params.toString()}` : '';
    return this.request(`/api/patients${q}`);
  },

  async getPatient(healthId) {
    return this.request(`/api/patients/${encodeURIComponent(healthId)}`);
  },

  async createPatient(patientData) {
    return this.request('/api/patients', {
      method: 'POST',
      body: JSON.stringify(patientData),
    });
  },

  async updatePatient(healthId, patientData) {
    return this.request(`/api/patients/${encodeURIComponent(healthId)}`, {
      method: 'PUT',
      body: JSON.stringify(patientData),
    });
  },

  // ---- Visit APIs ----
  async getVisits(healthId) {
    return this.request(`/api/patients/${encodeURIComponent(healthId)}/visits`);
  },

  async addVisit(healthId, visitData) {
    return this.request(`/api/patients/${encodeURIComponent(healthId)}/visits`, {
      method: 'POST',
      body: JSON.stringify(visitData),
    });
  },

  // ---- OCR API (TrOCR) ----
  async runOCR(imageFile) {
    const formData = new FormData();
    formData.append('file', imageFile);
    return this.request('/api/ocr', {
      method: 'POST',
      body: formData,
    });
  },

  // ---- AI Analysis API ----
  async analyzePatient(healthId) {
    return this.request(`/api/patients/${encodeURIComponent(healthId)}/analyze`, {
      method: 'POST',
    });
  },

  // ---- Field Visit APIs ----
  async getFieldVisits(skip = 0, limit = 50) {
    return this.request(`/api/field-visits?skip=${skip}&limit=${limit}`);
  },

  async createFieldVisit(visitData) {
    return this.request('/api/field-visits', {
      method: 'POST',
      body: JSON.stringify(visitData),
    });
  },

  // ---- Maps & Config APIs (Requirement 4) ----
  async getMapConfig() {
    return this.request('/api/config/maps');
  },

  // ---- Doctor Archive APIs (Requirement 8) ----
  async getArchive() {
    return this.request('/api/archive');
  },

  async downloadArchivePdf() {
    const token = this.getToken();
    const res = await fetch(`${this.BASE_URL}/api/archive/pdf`, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });
    if (!res.ok) {
      throw new Error(`Failed to download doctor archive: HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const user = this.getUserInfo();
    const docName = (user?.name || 'Doctor').replace(/[^a-zA-Z0-9]/g, '_');
    a.download = `AROG_Archive_${docName}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },


  // ---- Geolocation Helper ----
  async getCurrentLocation() {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error('Geolocation is not supported by your browser.'));
        return;
      }
      navigator.geolocation.getCurrentPosition(
        async (position) => {
          const lat = position.coords.latitude;
          const lng = position.coords.longitude;
          let locationName = '';
          try {
            // Optional reverse geocoding via OpenStreetMap Nominatim
            const res = await fetch(`https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json`, {
              headers: { 'Accept': 'application/json' },
            });
            if (res.ok) {
              const data = await res.json();
              const addr = data.address || {};
              locationName = addr.suburb || addr.town || addr.city || addr.county || addr.state || 'Field Care Station';
            }
          } catch (_) {
            locationName = 'Mobile Field Outpost';
          }
          resolve({
            latitude: lat,
            longitude: lng,
            locationName: locationName || 'Mobile Field Station',
          });
        },
        (error) => {
          let msg = 'Location access is required to automatically record the visit location.';
          if (error.code === error.TIMEOUT) msg = 'Location request timed out.';
          reject(new Error(msg));
        },
        { timeout: 8000, enableHighAccuracy: true }
      );
    });
  },

  // ---- Real QR Code Generator ----
  generateQR(text, containerEl, size = 88) {
    if (!containerEl) return;
    containerEl.innerHTML = '';
    if (typeof QRCode !== 'undefined') {
      try {
        new QRCode(containerEl, {
          text: text,
          width: size,
          height: size,
          colorDark: '#1e1b18',
          colorLight: '#ffffff',
          correctLevel: QRCode.CorrectLevel.M,
        });
        return;
      } catch (e) {
        console.warn('QRCode library error:', e);
      }
    }
    // Fallback if QRCode script is still loading: generate clean SVG QR
    containerEl.innerHTML = `
      <svg width="${size}" height="${size}" viewBox="0 0 100 100" class="text-primary bg-surface-container-lowest p-1 rounded">
        <rect x="0" y="0" width="100" height="100" fill="#ffffff"/>
        <rect x="8" y="8" width="28" height="28" fill="none" stroke="#1e1b18" stroke-width="5"/>
        <rect x="16" y="16" width="12" height="12" fill="#1e1b18"/>
        <rect x="64" y="8" width="28" height="28" fill="none" stroke="#1e1b18" stroke-width="5"/>
        <rect x="72" y="16" width="12" height="12" fill="#1e1b18"/>
        <rect x="8" y="64" width="28" height="28" fill="none" stroke="#1e1b18" stroke-width="5"/>
        <rect x="16" y="72" width="12" height="12" fill="#1e1b18"/>
        <rect x="44" y="14" width="12" height="12" fill="#1e1b18"/>
        <rect x="44" y="44" width="12" height="12" fill="#1e1b18"/>
        <rect x="14" y="44" width="12" height="12" fill="#1e1b18"/>
        <rect x="74" y="44" width="12" height="12" fill="#1e1b18"/>
        <rect x="44" y="74" width="12" height="12" fill="#1e1b18"/>
        <rect x="64" y="64" width="12" height="12" fill="#1e1b18"/>
        <rect x="78" y="78" width="14" height="14" fill="#1e1b18"/>
      </svg>
    `;
  },

  // ---- Navbar & Navigation Harmonization ----
  initNavbar() {
    const header = document.querySelector('header');
    if (!header) return;

    const path = window.location.pathname;
    const isHome = path.includes('arog_healthcare_continuity_home') || path === '/' || path.endsWith('index.html');
    const isPatients = path.includes('arog_patients_continuity_records');
    const isFieldVisits = path.includes('arog_field_visits_where_care_happened');

    const user = this.getUserInfo();
    const loggedIn = this.isLoggedIn();

    const logoSrc = "https://lh3.googleusercontent.com/aida/AEtjO1U52zKU-MZXsGgsqmuhWxEkTatrrqtmtmJuq4FvJ-oQKCunO5xnc5egcngEbP-wMzDa8LHQLCvnfCmaxSWJoCtsWsUYtnctm0WTfnB5-fV3illv9R6m3n7lI15ivGQ4HObxgrMZi7DgzNezoD8cs-EvquLu444iGOxsZ2NHQWz-P9JPZJ-dJScS4f2gtJvoOHpuvUtOpQZS1fUcAc8iWMpopHRXJ5q9E_21o3JpXiYQwQiDZ91-buc3qSE";

    header.className = "fixed top-0 inset-x-0 z-50 bg-surface/90 backdrop-blur-md shadow-[0_1px_8px_rgba(44,40,37,0.04)]";
    header.innerHTML = `
      <div class="h-20 max-w-7xl mx-auto px-6 lg:px-12 flex items-center justify-between">
        <div class="flex items-center gap-4">
          <a href="/frontend/arog_healthcare_continuity_home/code.html" class="flex items-center gap-3">
            <img alt="AROG Brand Logo" class="h-8 w-auto object-contain cursor-pointer" src="${logoSrc}" />
          </a>
          <span class="hidden sm:inline-block font-annotation-sm text-annotation-sm text-secondary tracking-wide border-l border-outline-variant/40 pl-3 italic">Continuity Ledger</span>
        </div>
        <div class="flex items-center gap-6 lg:gap-8">
          <nav class="hidden md:flex items-center gap-3">
            <a class="px-3.5 py-1.5 font-label-lg text-label-lg transition-colors rounded-full ${isHome ? 'bg-surface-container text-primary font-semibold' : 'text-on-surface-variant hover:text-on-surface'
      }" data-path="home" href="/frontend/arog_healthcare_continuity_home/code.html">Home</a>
            <a class="px-3.5 py-1.5 font-label-lg text-label-lg transition-colors rounded-full ${isPatients ? 'bg-surface-container text-primary font-semibold' : 'text-on-surface-variant hover:text-on-surface'
      }" data-path="patients" href="/frontend/arog_patients_continuity_records/code.html">Patients</a>
            <a class="px-3.5 py-1.5 font-label-lg text-label-lg transition-colors rounded-full ${isFieldVisits ? 'bg-surface-container text-primary font-semibold' : 'text-on-surface-variant hover:text-on-surface'
      }" data-path="timeline" href="/frontend/arog_field_visits_where_care_happened/code.html">Field Visits</a>
          </nav>
          <div class="flex items-center gap-4 pl-3 sm:border-l sm:border-outline-variant/40">
            ${loggedIn && user ? `
                <div id="nav-profile-trigger" class="flex items-center gap-3 pl-3 pr-1.5 py-1.5 rounded-full bg-surface-container-low hover:bg-surface-container transition-all cursor-pointer shadow-xs">
                  <div class="flex flex-col text-right hidden sm:flex">
                    <span id="nav-doctor-name" class="font-label-lg text-label-lg text-on-surface leading-none font-semibold">${user.name || 'Dr. Julian M. Aris, MD'}</span>
                    <span class="font-label-sm text-label-sm text-on-surface-variant">${user.role || 'Travelling Clinician'}</span>
                  </div>
                  <div class="w-8 h-8 rounded-full bg-primary text-on-primary flex items-center justify-center">
                    <span class="material-symbols-outlined text-[18px]">person</span>
                  </div>
                </div>
              ` : `
                <a class="px-4 py-1.5 rounded-full font-label-lg text-label-lg text-on-surface-variant hover:text-on-surface bg-surface-container-high/60 hover:bg-surface-container-high transition-all flex items-center gap-2" href="/frontend/arog_sign_in_clinical_portal/code.html">
                  <span>Sign In</span>
                  <span class="material-symbols-outlined text-[17px] text-primary">login</span>
                </a>
              `
      }
          </div>
        </div>
      </div>
    `;

    document.getElementById('nav-profile-trigger')?.addEventListener('click', () => {
      this.openProfileModal();
    });

    // Inject Doctor Profile Modal if not present
    this.ensureProfileModal();
  },

  // ---- Doctor Profile Modal ----
  ensureProfileModal() {
    if (document.getElementById('doctor-profile-modal')) return;

    const modal = document.createElement('div');
    modal.id = 'doctor-profile-modal';
    modal.className = 'fixed inset-0 z-50 bg-inverse-surface/40 backdrop-blur-xs flex items-center justify-center p-4 hidden opacity-0 transition-opacity duration-300';
    modal.innerHTML = `
      <div id="doctor-profile-panel" class="w-full max-w-md bg-surface-container-lowest rounded-2xl shadow-2xl p-6 sm:p-8 space-y-6 transform scale-95 transition-transform duration-300">
        <div class="flex items-start justify-between pb-4 border-b border-outline-variant/30">
          <div class="flex items-center gap-3">
            <div class="w-12 h-12 rounded-full bg-primary-fixed text-primary flex items-center justify-center shadow-inner">
              <span class="material-symbols-outlined text-[26px]">medical_services</span>
            </div>
            <div>
              <span class="font-label-sm text-label-sm uppercase tracking-wider text-primary font-semibold">Clinician Identity</span>
              <h3 id="profile-modal-name" class="font-headline-sm text-headline-sm text-on-surface font-serif">Doctor Profile</h3>
            </div>
          </div>
          <button id="close-profile-modal-btn" class="p-2 rounded-full hover:bg-surface-container text-on-surface-variant transition-colors">
            <span class="material-symbols-outlined text-[22px]">close</span>
          </button>
        </div>
        <div class="space-y-3 py-1 text-on-surface">
          <div class="p-3.5 rounded-xl bg-surface-container-low space-y-2">
            <div class="flex items-center justify-between text-xs">
              <span class="text-on-surface-variant font-medium">Email Address</span>
              <span id="profile-modal-email" class="font-mono text-on-surface font-semibold">-</span>
            </div>
            <div class="flex items-center justify-between text-xs">
              <span class="text-on-surface-variant font-medium">Clinical Role</span>
              <span id="profile-modal-role" class="text-primary font-semibold">Travelling Clinician</span>
            </div>
            <div class="flex items-center justify-between text-xs">
              <span class="text-on-surface-variant font-medium">Session Status</span>
              <span class="inline-flex items-center gap-1 text-primary font-medium">
                <span class="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
                Authenticated (JWT Active)
              </span>
            </div>
          </div>
          <div class="p-3 rounded-lg bg-surface-container/60 text-xs text-on-surface-variant">
            <p>Your clinician identity is automatically recorded on patient entries and field outreach stations for clinical auditability.</p>
          </div>
        </div>
        <div class="pt-4 border-t border-outline-variant/30 flex items-center justify-between gap-3">
          <button id="profile-modal-logout-btn" class="px-4 py-2 rounded-full bg-error-container/60 hover:bg-error-container text-on-error-container font-label-lg text-xs flex items-center gap-1.5 transition-all">
            <span class="material-symbols-outlined text-[16px]">logout</span>
            <span>Sign Out</span>
          </button>
          <button id="close-profile-modal-btn-2" class="px-5 py-2 rounded-full bg-surface-container hover:bg-surface-container-high text-on-surface font-label-lg text-xs transition-colors">
            Close
          </button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    const closeBtn1 = document.getElementById('close-profile-modal-btn');
    const closeBtn2 = document.getElementById('close-profile-modal-btn-2');
    const logoutBtn = document.getElementById('profile-modal-logout-btn');

    const closeModal = () => {
      modal.classList.add('opacity-0');
      document.getElementById('doctor-profile-panel')?.classList.add('scale-95');
      setTimeout(() => modal.classList.add('hidden'), 250);
    };

    closeBtn1?.addEventListener('click', closeModal);
    closeBtn2?.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });

    logoutBtn?.addEventListener('click', () => {
      AROG_API.logout();
    });
  },

  async openProfileModal() {
    this.ensureProfileModal();
    const modal = document.getElementById('doctor-profile-modal');
    const panel = document.getElementById('doctor-profile-panel');
    if (!modal) return;

    // Fetch latest profile from backend
    try {
      const p = await this.getProfile();
      document.getElementById('profile-modal-name').textContent = p.name;
      document.getElementById('profile-modal-email').textContent = p.email;
      document.getElementById('profile-modal-role').textContent = p.role || 'Travelling Clinician';
    } catch (_) {
      const u = this.getUserInfo();
      if (u) {
        document.getElementById('profile-modal-name').textContent = u.name;
        document.getElementById('profile-modal-email').textContent = u.email;
      }
    }

    modal.classList.remove('hidden');
    setTimeout(() => {
      modal.classList.remove('opacity-0');
      panel?.classList.remove('scale-95');
    }, 10);
  },
};

// Global initialization
if (typeof document !== 'undefined') {
  // Execute auth guard immediately before content render
  AROG_API.checkAuthGuard();

  document.addEventListener('DOMContentLoaded', () => {
    AROG_API.initNavbar();
  });
}
