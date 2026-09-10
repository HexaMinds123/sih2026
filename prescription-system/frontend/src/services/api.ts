import type { Analysis, Extraction, McpCheckResponse, UploadResult } from '../types/index'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init)
  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`
    try {
      const payload = await response.json()
      detail = payload.detail || detail
    } catch {
      // Keep the status-based message when the backend does not return JSON.
    }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

export function getApiBaseUrl() {
  return API_BASE_URL
}

export function healthCheck() {
  return request<{ status: string }>('/health')
}

export function uploadPrescription(file: File) {
  const body = new FormData()
  body.append('file', file)
  return request<UploadResult>('/upload-prescription', {
    method: 'POST',
    body,
  })
}

export function getPrescription(id: string) {
  return request<{ prescription_id: string; filename: string; status: string }>(
    `/prescription/${encodeURIComponent(id)}`,
  )
}

export function extractPrescription(id: string) {
  return request<Extraction>(`/prescription/${encodeURIComponent(id)}/extract`, { method: 'POST' })
}

export function analyzePrescription(id: string) {
  return request<Analysis>(`/prescription/${encodeURIComponent(id)}/analyze`, { method: 'POST' })
}

export function mcpCheck(id: string) {
  return request<McpCheckResponse>(`/prescription/${encodeURIComponent(id)}/mcp-check`, { method: 'POST' })
}
