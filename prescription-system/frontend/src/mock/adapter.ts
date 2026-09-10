import type { AgentStatus, Analysis, MCPServer } from '../types/index'
import { agentCatalog, alerts, mcpServers, notifications, orchestrationDemo, patients, vitalsFor } from './demoData'

export function listDemoPatients() {
  return patients
}

export function getDemoPatient(patientId: string) {
  return patients.find((patient) => patient.patient_id === patientId) ?? patients[0]
}

export function getDemoVitals(patientId: string) {
  return vitalsFor(patientId)
}

export function getDemoAlerts(patientId?: string) {
  return patientId ? alerts.filter((alert) => alert.patient_id === patientId) : alerts
}

export function getDemoNotifications(patientId?: string) {
  return patientId ? notifications.filter((item) => item.patient_id === patientId) : notifications
}

export function getDemoOrchestration() {
  return orchestrationDemo
}

export function mergeAgentCatalog(analysis: Analysis | null): AgentStatus[] {
  return agentCatalog.map((agent) => {
    if ((agent.id === 'medical_agent' || agent.id === 'clinical_mcp') && analysis) {
      const calls = analysis.audit.tools_called.map((call, index) => ({
        id: `live-${index}`,
        at: 'session',
        agent: agent.name,
        action: call.tool,
        input_summary: JSON.stringify(call.arguments),
        output_summary: call.result_received ? 'Result received' : 'Failed',
        ok: call.result_received,
      }))
      return {
        ...agent,
        status: 'online' as const,
        last_activity: `Live session ${analysis.prescription_id}`,
        recent_calls: calls,
        source: 'live' as const,
      }
    }
    return agent
  })
}

export function mergeMcpServers(analysis: Analysis | null, mcpConnected: boolean | null, mcpTools: string[], mcpError: string | null): MCPServer[] {
  return mcpServers.map((server) => {
    if (server.id !== 'clinical-guidelines') return server
    const calls = analysis?.audit.tools_called.map((call, index) => ({
      id: `mcp-${index}`,
      at: 'session',
      agent: 'Clinical MCP',
      action: call.tool,
      input_summary: JSON.stringify(call.arguments),
      output_summary: call.result_received ? 'Result received' : 'Failed',
      ok: call.result_received,
    })) ?? []
    return {
      ...server,
      connected: mcpConnected,
      tools: mcpTools.length
        ? mcpTools.map((name) => server.tools.find((tool) => tool.name === name) ?? { name, description: 'Reported by POST /prescription/{id}/mcp-check' })
        : server.tools,
      recent_calls: calls,
      errors: mcpError ? [mcpError] : [],
      source: mcpConnected === null ? 'demo' : 'live',
    }
  })
}
