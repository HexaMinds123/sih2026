import { DataSourceTag, DemoBanner, LevelBadge, PageHeader } from '../common/ui'
import { getDemoOrchestration, mergeAgentCatalog } from '../../mock/adapter'
import { useWorkspace } from '../../hooks/useWorkspace'

export function OrchestratorBoard() {
  const { lastAnalysis } = useWorkspace()
  const result = getDemoOrchestration()
  const agents = mergeAgentCatalog(lastAnalysis).filter((agent) => agent.layer !== 'mcp' || agent.id === 'clinical_mcp')

  return (
    <div className="page dash-page">
      <PageHeader
        eyebrow="Central reasoning"
        title="AI orchestrator"
        copy="The Healthcare Orchestrator is the master controller. The Medical Agent is a downstream specialist with no LLM and no orchestration role."
        extra={<DataSourceTag source="demo" label="Python class, no REST" />}
      />
      <DemoBanner />
      <div className="agent-status-row">
        {['Orchestrator', 'Medical Agent', 'EHR Agent', 'Notification Agent', 'Clinical MCP'].map((name) => (
          <article className="panel padded compact-card" key={name}>
            <p className="eyebrow">{name}</p>
            <div className="conn-dot demo" />
            <strong>Demo status</strong>
            <p className="muted">Not probed over HTTP</p>
          </article>
        ))}
      </div>
      <section className="panel padded">
        <div className="section-heading">
          <div><p className="eyebrow">Run</p><h2>Execution timeline</h2></div>
          <LevelBadge level={result.risk_level} />
        </div>
        <ol className="exec-timeline">
          {result.steps.map((step, index) => (
            <li key={step.id}>
              <span className="exec-index">{String(index + 1).padStart(2, '0')}</span>
              <div>
                <strong>{step.title}</strong>
                <p>{step.actor}</p>
                <p className="muted">In: {step.input}</p>
                <p className="muted">Out: {step.output}</p>
              </div>
              <span className="count-chip">{step.status}</span>
            </li>
          ))}
        </ol>
      </section>
      <div className="split-grid">
        <section className="panel padded">
          <p className="eyebrow">Inputs</p>
          <h2>Agent inputs</h2>
          {Object.entries(result.agent_inputs).map(([key, value]) => (
            <div className="code-block" key={key}><strong>{key}</strong><code>{value}</code></div>
          ))}
        </section>
        <section className="panel padded">
          <p className="eyebrow">Outputs</p>
          <h2>Agent outputs</h2>
          {Object.entries(result.agent_outputs).map(([key, value]) => (
            <div className="code-block" key={key}><strong>{key}</strong><code>{value}</code></div>
          ))}
        </section>
      </div>
      <section className="panel padded">
        <p className="eyebrow">Synthesis</p>
        <h2>Final orchestration result</h2>
        <p>{result.final_result}</p>
        <div className="detail-grid">
          <div><span className="field-label">Status</span><strong>{result.status}</strong></div>
          <div><span className="field-label">Approved</span><strong>{String(result.approved)}</strong></div>
          <div><span className="field-label">Human review</span><strong>{String(result.human_review_required)}</strong></div>
          <div><span className="field-label">Event</span><strong>{result.event_id}</strong></div>
        </div>
        {lastAnalysis && (
          <p className="muted">Latest live Medical Agent status from this browser session: {lastAnalysis.status} ({lastAnalysis.prescription_id}).</p>
        )}
      </section>
      <section className="panel padded">
        <p className="eyebrow">Catalog</p>
        <h2>Connected specialists</h2>
        <div className="agent-pills">
          {agents.map((agent) => (
            <span key={agent.id}>{agent.name} · {agent.source}</span>
          ))}
        </div>
      </section>
    </div>
  )
}
