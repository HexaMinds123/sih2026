import type { ReactNode } from 'react'
import { DEMO_ADAPTER_NOTE } from '../../mock/demoData'
import type { DataSourceKind } from '../../types/index'

export function valueOrUnavailable(value: unknown) {
  return value === null || value === undefined || value === '' ? 'Not available' : String(value)
}

export function DataSourceTag({ source, label }: { source: DataSourceKind; label?: string }) {
  return (
    <span className={`source-flag source-${source}`}>
      {source === 'live' ? 'Live API' : 'Demo adapter'}
      {label ? ` · ${label}` : ''}
    </span>
  )
}

export function DemoBanner({ children }: { children?: string }) {
  return <p className="demo-banner">{children || DEMO_ADAPTER_NOTE}</p>
}

export function PageHeader({
  eyebrow,
  title,
  copy,
  extra,
}: {
  eyebrow: string
  title: string
  copy: string
  extra?: ReactNode
}) {
  return (
    <header className="page-header">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="hero-copy">{copy}</p>
      </div>
      {extra}
    </header>
  )
}

export function LevelBadge({ level }: { level: string }) {
  const key = level.toLowerCase().replace(/ /g, '_')
  return <span className={`level-badge level-${key}`}>{level}</span>
}
