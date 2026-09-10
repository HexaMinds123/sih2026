import { useState } from 'react'
import { AlertTriangle, FlaskConical, LoaderCircle } from 'lucide-react'
import { analyzePrescription, extractPrescription, uploadPrescription } from '../../services/api'
import { useWorkspace } from '../../hooks/useWorkspace'
import { AnalysisPanel, ExtractionPanel, ExtractionStatus, UploadCard } from './PrescriptionWorkspace'
import { DataSourceTag } from '../common/ui'

export function PrescriptionFlow() {
  const { lastExtraction, lastAnalysis, recordUpload, recordExtraction, recordAnalysis } = useWorkspace()
  const [uploading, setUploading] = useState(false)
  const [extracting, setExtracting] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState('')

  async function handleFile(file: File) {
    setUploading(true)
    setError('')
    try {
      const upload = await uploadPrescription(file)
      recordUpload(upload)
      setExtracting(true)
      recordExtraction(await extractPrescription(upload.prescription_id))
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'The backend could not process this file.')
    } finally {
      setUploading(false)
      setExtracting(false)
    }
  }

  async function handleAnalyze() {
    if (!lastExtraction || analyzing) return
    setAnalyzing(true)
    setError('')
    try {
      recordAnalysis(await analyzePrescription(lastExtraction.prescription_id))
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Analysis could not be completed.')
    } finally {
      setAnalyzing(false)
    }
  }

  return (
    <div className="page">
      <section className="hero">
        <div>
          <p className="eyebrow">Medical & Pharmaceutical Agent</p>
          <h1>Turn a prescription into <em>traceable</em> evidence.</h1>
          <p className="hero-copy">Upload a prescription, review extraction, then run the deterministic Medical Agent. Clinical MCP / RAG stay on the backend. Status values are INFORMATIONAL, REVIEW_REQUIRED, CRITICAL_REVIEW_REQUIRED, or INSUFFICIENT_INFORMATION — never SAFE or APPROVED.</p>
        </div>
        <div className="hero-aside">
          <DataSourceTag source="live" label="FastAPI" />
          <span>01</span>
          <p>Extract<br />with context</p>
        </div>
      </section>
      <div className="workflow">
        <span className="active"><b>01</b> Upload</span><i />
        <span className={lastExtraction ? 'active' : ''}><b>02</b> Review</span><i />
        <span className={lastAnalysis ? 'active' : ''}><b>03</b> Analyze</span>
      </div>
      <UploadCard busy={uploading || extracting} onFile={handleFile} />
      {error && <div className="error-banner"><AlertTriangle size={18} /><div><strong>Something needs attention</strong><p>{error}</p></div></div>}
      <ExtractionStatus uploading={uploading} extracting={extracting} />
      {lastExtraction && (
        <>
          <ExtractionPanel extraction={lastExtraction} />
          <button className="analyze-button" disabled={analyzing} onClick={handleAnalyze}>
            {analyzing ? <LoaderCircle className="spin" size={19} /> : <FlaskConical size={19} />}
            {analyzing ? 'Analyzing evidence…' : 'Analyze Prescription'}
          </button>
        </>
      )}
      {lastAnalysis && <AnalysisPanel analysis={lastAnalysis} />}
    </div>
  )
}
