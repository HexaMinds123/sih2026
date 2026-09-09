import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import App from './App'

const extraction = {
  prescription_id: 'RX-TEST',
  ocr: { raw_text: 'Metformin 500 mg', ocr_confidence: 0.95, warnings: [], human_verification_required: false },
  prescription: {
    patient: { name: null, age: null, gender: null }, prescription_date: null, condition: 'Type 2 Diabetes',
    medications: [{ name: 'Metformin', strength: '500 mg', dose: null, frequency: 'twice daily', route: null, duration: null, instructions: null }],
    uncertain_medications: [], warnings: [],
  }, human_verification_required: false,
}

const analysis = {
  prescription_id: 'RX-TEST', status: 'REVIEW_REQUIRED', human_review_required: true,
  medications: [{ medication: 'Metformin', condition: 'Type 2 Diabetes', dosage: '500 mg twice daily', evidence_status: 'EVIDENCE_FOUND', evidence: [{ text: 'DailyMed evidence', source: 'DailyMed', document_id: 'doc-1', section: 'Dosing', page: null, version: 6, jurisdiction: 'United States', publication_date: '2026-06-24', source_url: null, retrieval_similarity_score: 0.6784 }] }],
  drug_interactions: { interaction_found: false, drugs: ['Metformin'], interactions: [] }, issues: ['Condition requires review'], audit: { tools_called: [{ tool: 'search_prescription_guidance', arguments: { medication: 'Metformin' }, result_received: true }] },
}

describe('Prescription dashboard', () => {
  it('renders upload and displays extracted fields and analysis evidence', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ prescription_id: 'RX-TEST', filename: 'rx.pdf', status: 'uploaded' }) })
      .mockResolvedValueOnce({ ok: true, json: async () => extraction })
      .mockResolvedValueOnce({ ok: true, json: async () => analysis }))
    render(<App />)
    expect(screen.getByRole('heading', { name: /upload a prescription/i })).toBeInTheDocument()
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(['pdf'], 'rx.pdf', { type: 'application/pdf' })
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => expect(screen.getByText('Metformin')).toBeInTheDocument())
    expect(screen.getAllByText('Not available').length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: /analyze prescription/i }))
    await waitFor(() => expect(screen.getByText('DailyMed evidence')).toBeInTheDocument())
    expect(screen.getByText('Retrieval Similarity Score')).toBeInTheDocument()
    expect(screen.getByText('REVIEW_REQUIRED')).toBeInTheDocument()
    expect(screen.getByText('Human review required')).toBeInTheDocument()
    expect(screen.queryByText('SAFE')).not.toBeInTheDocument()
  })

  it('rejects unsupported files before making a request', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [new File(['text'], 'notes.txt', { type: 'text/plain' })] } })
    expect(screen.getByText(/choose a jpg/i)).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
