import type { Analysis, Extraction } from '../types/index'

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

// ── Existing prescription endpoints (real) ────────────────────────────────────

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

// ── Health check (real) ───────────────────────────────────────────────────────

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await request<{ status: string }>('/health')
    return res.status === 'ok'
  } catch {
    return false
  }
}
