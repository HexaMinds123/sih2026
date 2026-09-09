import type { Analysis, Extraction } from './types'

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

export function uploadPrescription(file: File) {
  const body = new FormData()
  body.append('file', file)
  return request<{ prescription_id: string; filename: string; status: string }>('/upload-prescription', {
    method: 'POST',
    body,
  })
}

export function extractPrescription(id: string) {
  return request<Extraction>(`/prescription/${encodeURIComponent(id)}/extract`, { method: 'POST' })
}

export function analyzePrescription(id: string) {
  return request<Analysis>(`/prescription/${encodeURIComponent(id)}/analyze`, { method: 'POST' })
}
