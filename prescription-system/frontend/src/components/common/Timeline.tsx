import type { AgentEvent } from '../../types/index'
import { CheckCircle2, AlertTriangle, AlertOctagon, Info } from 'lucide-react'

const ICON_MAP = {
  ok: <CheckCircle2 size={15} className="tl-icon-ok" />,
  warn: <AlertTriangle size={15} className="tl-icon-warn" />,
  error: <AlertOctagon size={15} className="tl-icon-err" />,
  info: <Info size={15} className="tl-icon-info" />,
}

export function Timeline({ events }: { events: AgentEvent[] }) {
  return (
    <ol className="timeline">
      {events.map((ev) => (
        <li key={ev.id} className={`tl-item tl-${ev.status}`}>
          <div className="tl-icon">{ICON_MAP[ev.status]}</div>
          <div className="tl-body">
            <div className="tl-top">
              <span className="tl-agent">{ev.agent}</span>
              <span className="tl-time">{new Date(ev.timestamp).toLocaleTimeString()}</span>
            </div>
            <strong className="tl-event">{ev.event}</strong>
            <p className="tl-detail">{ev.detail}</p>
          </div>
        </li>
      ))}
    </ol>
  )
}

// Compact escalation chain (used in alert cards)
interface ChainStep {
  step: string
  actor: string
  timestamp: string
  status: 'done' | 'pending' | 'skipped'
}
export function EscalationChain({ steps }: { steps: ChainStep[] }) {
  return (
    <div className="escalation-chain">
      {steps.map((s, i) => (
        <div key={i} className={`ec-step ec-${s.status}`}>
          <div className="ec-dot" />
          {i < steps.length - 1 && <div className="ec-line" />}
          <div className="ec-content">
            <span className="ec-label">{s.step}</span>
            <span className="ec-meta">{s.actor} · {s.timestamp}</span>
          </div>
        </div>
      ))}
    </div>
  )
}
