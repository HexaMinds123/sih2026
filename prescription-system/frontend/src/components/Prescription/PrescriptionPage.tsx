import { useRef, useState } from 'react'
import {
  AlertTriangle, ArrowUpRight, CheckCircle2, ChevronDown, ChevronUp,
  FlaskConical, LoaderCircle, ShieldAlert, UploadCloud
} from 'lucide-react'
import { analyzePrescription, extractPrescription, uploadPrescription } from '../../services/api'
import { StatusBadge } from '../common/Badges'
import type { Analysis, Evidence, Extraction, Medication } from '../../types/index'

const MAX_FILE_SIZE = 10 * 1024 * 1024
const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'application/pdf']
const ACCEPTED_EXTENSIONS = '.jpg,.jpeg,.png,.pdf'

function valueOrUnavailable(value: unknown) {
  return value === null || value === undefined || value === '' ? 'Not available' : String(value)
}

// ── Upload Card ──────────────────────────────────────────────────────────────
function UploadCard({ busy, onFile }: { busy: boolean; onFile: (file: File) => void }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [error, setError] = useState('')

  function validate(file: File) {
    const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
    if (!ACCEPTED_TYPES.includes(file.type) || !['.jpg', '.jpeg', '.png', '.pdf'].includes(ext)) {
      setError('Choose a JPG, JPEG, PNG, or PDF prescription.')
      return
    }
    if (file.size > MAX_FILE_SIZE) { setError('File exceeds 10 MB limit.'); return }
    setError(''); onFile(file)
  }

  return (
    <section className="upload-card panel">
      <div className="upload-mark"><UploadCloud size={26} strokeWidth={1.8} /></div>
      <div>
        <p className="eyebrow">Secure intake</p>
        <h2>Upload a prescription</h2>
        <p className="muted">Bring in a clear image or PDF. The document stays private in the backend upload store.</p>
      </div>
      <input ref={inputRef} type="file" accept={ACCEPTED_EXTENSIONS} hidden
        onChange={(e) => e.target.files?.[0] && validate(e.target.files[0])} />
      <button className="primary-button" disabled={busy} onClick={() => inputRef.current?.click()}>
        {busy ? <LoaderCircle className="spin" size={18} /> : <UploadCloud size={18} />}
        {busy ? 'Uploading…' : 'Choose file'}
      </button>
      <p className="file-note">PDF, JPG, JPEG, PNG · max 10 MB</p>
      {error && <p className="inline-error"><AlertTriangle size={15} />{error}</p>}
    </section>
  )
}

// ── Extraction Panel ─────────────────────────────────────────────────────────
function ExtractionPanel({ extraction }: { extraction: Extraction }) {
  const { prescription, ocr } = extraction
  return (
    <section className="panel extraction-panel">
      <div className="section-heading">
        <div><p className="eyebrow">Structured record</p><h2>Prescription details</h2></div>
        <span className="id-chip">{extraction.prescription_id}</span>
      </div>
      <div className="detail-grid">
        <div><span className="field-label">Patient</span><strong>{valueOrUnavailable(prescription.patient.name)}</strong></div>
        <div><span className="field-label">Age</span><strong>{valueOrUnavailable(prescription.patient.age)}</strong></div>
        <div><span className="field-label">Gender</span><strong>{valueOrUnavailable(prescription.patient.gender)}</strong></div>
        <div><span className="field-label">Condition</span><strong>{valueOrUnavailable(prescription.condition)}</strong></div>
        <div><span className="field-label">Prescription date</span><strong>{valueOrUnavailable(prescription.prescription_date)}</strong></div>
        <div><span className="field-label">OCR confidence</span>
          <strong>{ocr.ocr_confidence === null ? 'Not available' : `${Math.round(ocr.ocr_confidence * 100)}%`}</strong>
        </div>
      </div>
      <div className="subsection-heading"><FlaskConical size={18} /><h3>Medications</h3></div>
      <div className="medication-list">
        {prescription.medications.length === 0
          ? <p className="empty-state">No medication was extracted.</p>
          : prescription.medications.map((med, i) => <MedicationCard key={`${med.name}-${i}`} medication={med} />)}
      </div>
      {(ocr.warnings.length > 0 || prescription.warnings.length > 0 || prescription.uncertain_medications.length > 0) &&
        <WarningsBox extraction={extraction} />}
    </section>
  )
}

function MedicationCard({ medication }: { medication: Medication }) {
  return (
    <article className="medication-card">
      <div className="medication-name"><span className="medication-index">Rx</span><strong>{medication.name}</strong></div>
      <div><span className="field-label">Strength</span><span>{valueOrUnavailable(medication.strength)}</span></div>
      <div><span className="field-label">Dose</span><span>{valueOrUnavailable(medication.dose)}</span></div>
      <div><span className="field-label">Frequency</span><span>{valueOrUnavailable(medication.frequency)}</span></div>
      <div><span className="field-label">Route</span><span>{valueOrUnavailable(medication.route)}</span></div>
      <div><span className="field-label">Duration</span><span>{valueOrUnavailable(medication.duration)}</span></div>
    </article>
  )
}

function WarningsBox({ extraction }: { extraction: Extraction }) {
  const warnings = [
    ...extraction.ocr.warnings,
    ...extraction.prescription.warnings.map(w => w.reason),
    ...extraction.prescription.uncertain_medications.map(w => `${w.text}: ${w.reason}`),
  ]
  return (
    <div className="warning-box">
      <div className="warning-title"><AlertTriangle size={16} />Extraction warnings</div>
      {warnings.map((w, i) => <p key={`${w}-${i}`}>{w}</p>)}
      <strong>{extraction.human_verification_required ? 'Human review required' : 'No human review flag returned'}</strong>
    </div>
  )
}

// ── Evidence Item ────────────────────────────────────────────────────────────
function EvidenceItem({ item }: { item: Evidence }) {
  return (
    <article className="evidence-item">
      <div className="evidence-topline">
        <span className="source-tag">{valueOrUnavailable(item.source)}</span>
        <span className="score">Retrieval Similarity Score <strong>{item.retrieval_similarity_score === null ? 'Not available' : item.retrieval_similarity_score.toFixed(4)}</strong></span>
      </div>
      <p className="evidence-text">{valueOrUnavailable(item.text)}</p>
      <div className="provenance-grid">
        <span>Document ID<strong>{valueOrUnavailable(item.document_id)}</strong></span>
        <span>Section<strong>{valueOrUnavailable(item.section)}</strong></span>
        <span>Version<strong>{valueOrUnavailable(item.version)}</strong></span>
        <span>Published<strong>{valueOrUnavailable(item.publication_date)}</strong></span>
        <span>Jurisdiction<strong>{valueOrUnavailable(item.jurisdiction)}</strong></span>
      </div>
      {item.source_url && <a className="source-link" href={item.source_url} target="_blank" rel="noreferrer">Open source <ArrowUpRight size={14} /></a>}
    </article>
  )
}

// ── Analysis Panel ───────────────────────────────────────────────────────────
function AnalysisPanel({ analysis }: { analysis: Analysis }) {
  const [auditOpen, setAuditOpen] = useState(false)
  const interactions = analysis.drug_interactions.interactions || []

  return (
    <section className="analysis-stack">
      {/* Status */}
      <section className="status-panel panel">
        <div>
          <p className="eyebrow">Agent result</p>
          <h2>Analysis status</h2>
          <p className="muted">Reference-based decision support. This result is not a diagnosis or approval.</p>
        </div>
        <div className="status-wrap">
          <StatusBadge status={analysis.status} />
          <span className={analysis.human_review_required ? 'review-flag' : 'review-flag quiet'}>
            {analysis.human_review_required ? 'Human review required' : 'No human review flag returned'}
          </span>
        </div>
      </section>

      {/* Clinical evidence */}
      <section className="panel">
        <div className="section-heading">
          <div><p className="eyebrow">Medication-by-medication</p><h2>Clinical evidence</h2></div>
          <span className="count-chip">{analysis.medications.length} records</span>
        </div>
        <p className="score-note">Retrieval similarity indicates how closely evidence matched the query. It is not a medical safety score, confidence score, or probability.</p>
        {analysis.medications.map((med, i) => (
          <article className="medication-result" key={`${med.medication}-${i}`}>
            <div className="result-heading">
              <div>
                <h3>{valueOrUnavailable(med.medication)}</h3>
                <p>{valueOrUnavailable(med.dosage)} · {valueOrUnavailable(med.condition)}</p>
              </div>
              <span className={`evidence-pill ${med.evidence_status === 'EVIDENCE_FOUND' ? 'found' : 'missing'}`}>{med.evidence_status}</span>
            </div>
            {med.evidence.length
              ? med.evidence.map((ev, ei) => <EvidenceItem key={`${ev.document_id}-${ei}`} item={ev} />)
              : <p className="empty-state">No sufficiently relevant clinical evidence found.</p>}
          </article>
        ))}
      </section>

      {/* Drug interactions */}
      <section className="panel">
        <div className="section-heading">
          <div><p className="eyebrow">Interaction review</p><h2>Drug interactions</h2></div>
          <span className={analysis.drug_interactions.interaction_found ? 'count-chip alert' : 'count-chip'}>
            {analysis.drug_interactions.interaction_found ? `${interactions.length} found` : 'None returned'}
          </span>
        </div>
        {interactions.length
          ? interactions.map((ix, i) => (
            <div className="interaction-row" key={`${ix.warning}-${i}`}>
              <ShieldAlert size={20} />
              <div>
                <strong>{ix.drugs?.join(' + ') || 'Medication pair'}</strong>
                <p>{ix.warning || 'No description returned.'}</p>
              </div>
              <span className="severity">{ix.severity || 'Not available'}</span>
            </div>
          ))
          : <p className="empty-state"><CheckCircle2 size={18} />No interaction was returned for this prescription.</p>}
      </section>

      {/* Issues */}
      <section className="panel">
        <div className="section-heading">
          <div><p className="eyebrow">Attention</p><h2>Issues and warnings</h2></div>
          <span className="count-chip">{analysis.issues.length}</span>
        </div>
        {analysis.issues.length
          ? <ul className="issue-list">{analysis.issues.map((issue, i) => <li key={`${issue}-${i}`}><AlertTriangle size={16} />{issue}</li>)}</ul>
          : <p className="empty-state"><CheckCircle2 size={18} />No issues were returned.</p>}
      </section>

      {/* Audit trail */}
      <section className="panel audit-panel">
        <button className="audit-toggle" onClick={() => setAuditOpen(o => !o)}>
          <span><p className="eyebrow">Traceability</p><strong>Audit trail</strong></span>
          {auditOpen ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
        </button>
        {auditOpen && (
          <div className="audit-list">
            {analysis.audit.tools_called.map((call, i) => (
              <div className="audit-row" key={`${call.tool}-${i}`}>
                <span className="audit-dot" />
                <div>
                  <strong>{call.tool}</strong>
                  <code>{JSON.stringify(call.arguments)}</code>
                </div>
                <span className={call.result_received ? 'audit-success' : 'audit-failure'}>
                  {call.result_received ? 'Result received' : 'Failed'}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </section>
  )
}

// ── Prescription Page (main export) ─────────────────────────────────────────
export function PrescriptionPage() {
  const [uploading, setUploading] = useState(false)
  const [extracting, setExtracting] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [extraction, setExtraction] = useState<Extraction | null>(null)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [error, setError] = useState('')

  async function handleFile(file: File) {
    setUploading(true); setError(''); setAnalysis(null); setExtraction(null)
    try {
      const upload = await uploadPrescription(file)
      setExtracting(true)
      setExtraction(await extractPrescription(upload.prescription_id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The backend could not process this file.')
    } finally { setUploading(false); setExtracting(false) }
  }

  async function handleAnalyze() {
    if (!extraction || analyzing) return
    setAnalyzing(true); setError('')
    try { setAnalysis(await analyzePrescription(extraction.prescription_id)) }
    catch (err) { setError(err instanceof Error ? err.message : 'Analysis could not be completed.') }
    finally { setAnalyzing(false) }
  }

  return (
    <div className="page-content">
      <div className="page-header">
        <div>
          <p className="eyebrow">Clinical workspace</p>
          <h1 className="page-title">Prescription Analysis</h1>
        </div>
        <div className="workflow">
          <span className="active"><b>01</b> Upload</span>
          <i />
          <span className={extraction ? 'active' : ''}><b>02</b> Review</span>
          <i />
          <span className={analysis ? 'active' : ''}><b>03</b> Analyze</span>
        </div>
      </div>

      <UploadCard busy={uploading || extracting} onFile={handleFile} />

      {error && (
        <div className="error-banner">
          <AlertTriangle size={18} />
          <div><strong>Something needs attention</strong><p>{error}</p></div>
        </div>
      )}

      {extracting && (
        <div className="loading-line">
          <LoaderCircle className="spin" size={18} />Reading prescription and structuring fields…
        </div>
      )}

      {extraction && (
        <>
          <ExtractionPanel extraction={extraction} />
          <button className="analyze-button" disabled={analyzing} onClick={handleAnalyze}>
            {analyzing ? <LoaderCircle className="spin" size={19} /> : <FlaskConical size={19} />}
            {analyzing ? 'Analyzing evidence…' : 'Analyze Prescription'}
          </button>
        </>
      )}

      {analysis && <AnalysisPanel analysis={analysis} />}
    </div>
  )
}
