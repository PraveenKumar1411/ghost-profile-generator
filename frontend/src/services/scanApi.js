import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1',
  timeout: 120000,
})

api.interceptors.request.use((config) => {
  config.metadata = {
    startedAt: performance.now(),
    timeout: config.timeout,
  }
  console.info('[scan-api] request', {
    method: config.method?.toUpperCase(),
    url: `${config.baseURL ?? ''}${config.url ?? ''}`,
    timeout: config.timeout,
  })
  return config
})

api.interceptors.response.use(
  (response) => {
    const metadata = response.config.metadata
    console.info('[scan-api] response', {
      method: response.config.method?.toUpperCase(),
      url: `${response.config.baseURL ?? ''}${response.config.url ?? ''}`,
      durationMs: metadata ? Math.round(performance.now() - metadata.startedAt) : null,
      timeout: metadata?.timeout ?? response.config.timeout,
      status: response.status,
    })
    return response
  },
  (error) => {
    const config = error.config
    const metadata = config?.metadata
    console.error('[scan-api] error', {
      method: config?.method?.toUpperCase(),
      url: `${config?.baseURL ?? ''}${config?.url ?? ''}`,
      durationMs: metadata ? Math.round(performance.now() - metadata.startedAt) : null,
      timeout: metadata?.timeout ?? config?.timeout,
      status: error.response?.status ?? null,
      code: error.code,
      message: error.message,
    })
    return Promise.reject(error)
  },
)

export async function scanUsername(username) {
  const { data } = await api.get(`/scan/${encodeURIComponent(username)}`)
  return data
}

export async function startScan(username) {
  const { data } = await api.post('/scan/start', { username })
  return data
}

export async function getScanStatus(scanId) {
  const { data } = await api.get(`/scan/status/${encodeURIComponent(scanId)}`)
  return data
}

export async function getScanResult(scanId) {
  const { data } = await api.get(`/scan/result/${encodeURIComponent(scanId)}`)
  return data
}

export async function downloadReport(value, byReportId = false) {
  const path = byReportId ? `/report/id/${encodeURIComponent(value)}` : `/report/${encodeURIComponent(value)}`
  const { data } = await api.get(path, {
    responseType: 'blob',
  })
  return data
}

export async function getScanHistory() {
  const { data } = await api.get('/scans')
  return data
}

export async function getAnalytics() {
  const { data } = await api.get('/scans/analytics/summary')
  return data
}

export async function getSystemStatus() {
  const { data } = await api.get('/health')
  return data
}

export function getApiErrorMessage(error) {
  if (error.response?.data?.detail) return error.response.data.detail
  if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
    return 'Scan is taking longer than expected. Please retry in a moment.'
  }
  if (error.message) return error.message
  if (!error.response) return 'Unable to reach the scanner. Is the API running?'
  return 'The scan could not be completed. Please try again.'
}
