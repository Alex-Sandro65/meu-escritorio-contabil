import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
})

// Interceptor de token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Interceptor de refresh token
api.interceptors.response.use(
  (r) => r,
  async (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Auth
export const authAPI = {
  login: (email: string, password: string) =>
    api.post('/auth/login', new URLSearchParams({ username: email, password }), {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    }),
  register: (data: any) => api.post('/auth/register', data),
  setupMFA: () => api.post('/auth/mfa/setup'),
  enableMFA: (token: string, tempToken: string) =>
    api.post('/auth/mfa/enable', { token, temp_token: tempToken }),
}

// Balancete
export const balanceteAPI = {
  importar: (formData: FormData) =>
    api.post('/balancetes/importar', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  get: (id: string) => api.get(`/balancetes/${id}`),
  listar: (empresaId: string) => api.get(`/balancetes/empresa/${empresaId}`),
}

// Conciliação
export const conciliacaoAPI = {
  bancaria: (formData: FormData) =>
    api.post('/conciliacoes/bancaria', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  get: (id: string) => api.get(`/conciliacoes/${id}`),
}

// Dashboard
export const dashboardAPI = {
  resumo: () => api.get('/dashboard/resumo'),
  empresa: (id: string, competencia?: string) =>
    api.get(`/dashboard/empresa/${id}`, { params: { competencia } }),
}

// Auditoria
export const auditoriaAPI = {
  materialidade: (data: any) => api.post('/auditoria/materialidade', data),
  analiseHorizontal: (atual: string, anterior: string) =>
    api.post('/auditoria/analise-horizontal', null, {
      params: { balancete_atual_id: atual, balancete_anterior_id: anterior },
    }),
  indices: (balanceteId: string) => api.post(`/auditoria/indices/${balanceteId}`),
  analiseIA: (balanceteId: string) => api.post(`/auditoria/analise-ia/${balanceteId}`),
}
