import axios from 'axios';

// ---------------------------------------------------------------------------
// Axios instance
// ---------------------------------------------------------------------------
const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || '/api',
  headers: { 'Content-Type': 'application/json' },
});

// -- Request interceptor: attach Bearer token ---
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// -- Response interceptor: redirect to /login on 401 ---
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  },
);

// ---------------------------------------------------------------------------
// API modules
// ---------------------------------------------------------------------------

// -- Auth --
export const authAPI = {
  login: (email, password) => api.post('/auth/login', { email, password }),
  register: (data) => api.post('/auth/register', data),
  getMe: () => api.get('/users/me'),
};

// -- Users --
export const usersAPI = {
  getAll: () => api.get('/users/'),
  update: (id, data) => api.put(`/users/${id}`, data),
  delete: (id) => api.delete(`/users/${id}`),
  changePassword: (data) => api.post('/users/me/change-password', data),
};

// -- Projects --
export const projectsAPI = {
  getAll: (params = {}) => api.get('/projects/', { params }),
  getById: (id) => api.get(`/projects/${id}`),
  create: (data) => api.post('/projects/', data),
  update: (id, data) => api.put(`/projects/${id}`, data),
  updateAppProfile: (id, data) => api.put(`/projects/${id}/app-profile`, data),
  archive: (id) => api.post(`/projects/${id}/archive`),
  delete: (id) => api.delete(`/projects/${id}`),
  // Feature 2: Test Coverage Score
  getCoverage: (id) => api.get(`/projects/${id}/coverage`),
  // Feature 3: Profile Validation
  validateProfile: (id) => api.post(`/projects/${id}/app-profile/validate`),
  // Feature 4: OpenAPI Auto-Discovery
  discoverOpenAPI: (id, data) => api.post(`/projects/${id}/app-profile/discover`, data),
  // AI UI Discovery (Playwright + LLM vision)
  discoverUI: (id, data) => api.post(`/projects/${id}/app-profile/discover-ui`, data),
};

// -- Requirements --
export const requirementsAPI = {
  list: (projectId) => api.get(`/projects/${projectId}/requirements`),
  create: (projectId, data) => api.post(`/projects/${projectId}/requirements`, data),
  update: (projectId, reqId, data) => api.put(`/projects/${projectId}/requirements/${reqId}`, data),
  delete: (projectId, reqId) => api.delete(`/projects/${projectId}/requirements/${reqId}`),
  upload: (projectId, data) => api.post(`/projects/${projectId}/requirements/upload`, data),
  extract: (projectId, data) => api.post(`/projects/${projectId}/requirements/extract`, data),
};

// -- Test Cases --
export const testCasesAPI = {
  list: (projectId, params = {}) => api.get(`/projects/${projectId}/test-cases`, { params }),
  generate: (projectId, data) => api.post(`/projects/${projectId}/test-cases/generate`, data),
  create: (projectId, data) => api.post(`/projects/${projectId}/test-cases`, data),
  getById: (projectId, tcId) => api.get(`/projects/${projectId}/test-cases/${tcId}`),
  update: (projectId, tcId, data) => api.put(`/projects/${projectId}/test-cases/${tcId}`, data),
  delete: (projectId, tcId) => api.delete(`/projects/${projectId}/test-cases/${tcId}`),
  bulkDelete: (projectId, testCaseIds) =>
    api.post(`/projects/${projectId}/test-cases/bulk-delete`, { test_case_ids: testCaseIds }),
  bulkStatus: (projectId, testCaseIds, status) =>
    api.post(`/projects/${projectId}/test-cases/bulk-status`, { test_case_ids: testCaseIds, status }),
  rate: (projectId, tcId, data) => api.post(`/projects/${projectId}/test-cases/${tcId}/rate`, data),
  exportExcel: (projectId, data) =>
    api.post(`/projects/${projectId}/test-cases/export`, data, { responseType: 'blob' }),
  downloadTemplate: (projectId) =>
    api.get(`/projects/${projectId}/test-cases/upload-template`, { responseType: 'blob' }),
  bulkUpload: (projectId, file) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/projects/${projectId}/test-cases/bulk-upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  // Feature 6: Chat-Based Generation
  chatGenerate: (projectId, data) => api.post(`/projects/${projectId}/test-cases/chat`, data),
};

// -- Templates --
export const templatesAPI = {
  getAll: (params = {}) => api.get('/templates/', { params }),
  getById: (id) => api.get(`/templates/${id}`),
  create: (data) => api.post('/templates/', data),
  update: (id, data) => api.put(`/templates/${id}`, data),
  delete: (id) => api.delete(`/templates/${id}`),
  preview: (id) => api.get(`/templates/${id}/preview`),
};

// -- Feedback --
export const feedbackAPI = {
  getMetrics: (params = {}) => api.get('/feedback/metrics', { params }),
  getCorrections: (params = {}) => api.get('/feedback/corrections', { params }),
};

// -- Knowledge --
export const knowledgeAPI = {
  list: (params = {}) => api.get('/knowledge/entries', { params }),
  search: (params) => api.get('/knowledge/search', { params }),
  create: (data) => api.post('/knowledge/', data),
  update: (id, data) => api.put(`/knowledge/entries/${id}`, data),
  delete: (id) => api.delete(`/knowledge/entries/${id}`),
  getStats: () => api.get('/knowledge/stats'),
  seed: () => api.post('/knowledge/seed'),
};

// -- Reviews --
export const reviewsAPI = {
  getPending: () => api.get('/reviews/pending'),
};

// -- Settings --
export const settingsAPI = {
  getLLM: () => api.get('/settings/llm'),
  updateLLM: (data) => api.put('/settings/llm', data),
  getProviders: () => api.get('/settings/llm/providers'),
};

// -- Test Plans --
export const testPlansAPI = {
  list: (projectId, params = {}) => api.get(`/projects/${projectId}/test-plans`, { params }),
  create: (projectId, data) => api.post(`/projects/${projectId}/test-plans`, data),
  getById: (projectId, planId) => api.get(`/projects/${projectId}/test-plans/${planId}`),
  update: (projectId, planId, data) => api.put(`/projects/${projectId}/test-plans/${planId}`, data),
  delete: (projectId, planId) => api.delete(`/projects/${projectId}/test-plans/${planId}`),
  // Checkpoints
  listCheckpoints: (projectId, planId) => api.get(`/projects/${projectId}/test-plans/${planId}/checkpoints`),
  createCheckpoint: (projectId, planId, data) => api.post(`/projects/${projectId}/test-plans/${planId}/checkpoints`, data),
  reviewCheckpoint: (projectId, cpId, data) => api.patch(`/projects/${projectId}/checkpoints/${cpId}`, data),
  // Reports
  getTraceability: (projectId, planId) => api.get(`/projects/${projectId}/test-plans/${planId}/traceability`),
  getSummary: (projectId, planId) => api.get(`/projects/${projectId}/test-plans/${planId}/summary`),
};

// -- Execution Results --
export const executionsAPI = {
  list: (projectId, params = {}) => api.get(`/projects/${projectId}/executions`, { params }),
  getById: (projectId, execId) => api.get(`/projects/${projectId}/executions/${execId}`),
  review: (projectId, execId, data) => api.post(`/projects/${projectId}/executions/${execId}/review`, data),
};

// -- Agent Key --
export const agentKeyAPI = {
  generate: (projectId) => api.post(`/projects/${projectId}/agent-key`),
  revoke: (projectId) => api.delete(`/projects/${projectId}/agent-key`),
};

export default api;
