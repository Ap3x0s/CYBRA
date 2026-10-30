// Thin API client. Keeping fetch calls here means the UI never builds a URL.
let csrf = ''

export function setCsrf(token) {
  csrf = token || ''
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

async function request(path, { method = 'GET', body, form } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (method !== 'GET' && csrf) headers['x-csrf-token'] = csrf

  const response = await fetch('/api/v1' + path, {
    method,
    headers,
    credentials: 'same-origin',
    body: form ? form : body === undefined ? undefined : JSON.stringify(body),
  })

  if (response.status === 204) return null
  const text = await response.text()
  let payload = null
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = { detail: text }
    }
  }
  if (!response.ok) {
    const detail = payload?.detail
    const message =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((item) => item.msg || JSON.stringify(item)).join('; ')
          : `HTTP ${response.status}`
    throw new ApiError(message, response.status)
  }
  return payload
}

/** Build a query string, dropping empty values.
 *  URLSearchParams turns `undefined` into the literal "undefined", which the
 *  backend would then treat as a filter value and return nothing. */
function query(params) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    search.set(key, value)
  }
  const text = search.toString()
  return text ? '?' + text : ''
}

export const api = {
  // auth
  login: (email, password) =>
    request('/auth/login', { method: 'POST', body: { email, password } }),
  logout: () => request('/auth/logout', { method: 'POST' }),
  me: () => request('/auth/me'),
  changePassword: (current_password, new_password) =>
    request('/auth/password', { method: 'POST', body: { current_password, new_password } }),

  // users
  users: () => request('/users'),
  createUser: (payload) => request('/users', { method: 'POST', body: payload }),
  updateUser: (id, payload) => request(`/users/${id}`, { method: 'PATCH', body: payload }),

  // endpoints & targets
  endpoints: () => request('/endpoints'),
  createEndpoint: (payload) => request('/endpoints', { method: 'POST', body: payload }),
  updateEndpoint: (id, payload) => request(`/endpoints/${id}`, { method: 'PUT', body: payload }),
  deleteEndpoint: (id) => request(`/endpoints/${id}`, { method: 'DELETE' }),
  probeEndpoint: (id) => request(`/endpoints/${id}/probe`, { method: 'POST' }),

  targets: () => request('/targets'),
  createTarget: (payload) => request('/targets', { method: 'POST', body: payload }),
  deleteTarget: (id) => request(`/targets/${id}`, { method: 'DELETE' }),

  // datasets
  datasets: () => request('/datasets'),
  datasetTemplates: () => request('/datasets/templates'),
  seedDataset: (name) => request('/datasets/seed', { method: 'POST', body: { name } }),
  importDataset: (name, file) => {
    const form = new FormData()
    form.append('file', file)
    return request(`/datasets/import?name=${encodeURIComponent(name)}`, {
      method: 'POST',
      form,
    })
  },
  cases: (versionId) => request(`/datasets/${versionId}/cases`),
  forkVersion: (versionId, payload = {}) =>
    request(`/datasets/${versionId}/fork`, { method: 'POST', body: payload }),
  updateCase: (versionId, caseId, payload) =>
    request(`/datasets/${versionId}/cases/${caseId}`, { method: 'PUT', body: payload }),
  diffVersions: (left, right) => request(`/datasets/diff?left=${left}&right=${right}`),

  // runs
  runs: (limit = 50) => request(`/runs?limit=${limit}`),
  run: (id) => request(`/runs/${id}`),
  createRun: (payload) => request('/runs', { method: 'POST', body: payload }),
  cancelRun: (id) => request(`/runs/${id}/cancel`, { method: 'POST' }),
  runProgress: (id) => request(`/runs/${id}/progress`),
  runFindings: (id, params = {}) => request(`/runs/${id}/findings${query(params)}`),
  runReport: (id, fmt = 'json') => request(`/runs/${id}/report${query({ fmt })}`),

  // metrics & capabilities
  metricsCatalog: () => request('/metrics/catalog'),
  metricsSeries: (params = {}) => request(`/metrics/series${query(params)}`),
  capabilities: () => request('/capabilities'),
}
