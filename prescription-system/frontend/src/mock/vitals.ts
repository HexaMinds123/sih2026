import type { VitalReading, VitalStatus } from '../types/index'

// DEMO DATA — simulated vitals stream for P001
export const MOCK_VITALS_HISTORY: VitalReading[] = [
  { timestamp: '2026-09-10T05:00:00Z', heart_rate: 74, spo2: 97, systolic_bp: 128, diastolic_bp: 82, temperature: 36.7, glucose: 118 },
  { timestamp: '2026-09-10T06:00:00Z', heart_rate: 71, spo2: 98, systolic_bp: 124, diastolic_bp: 80, temperature: 36.6, glucose: 112 },
  { timestamp: '2026-09-10T07:00:00Z', heart_rate: 78, spo2: 97, systolic_bp: 131, diastolic_bp: 84, temperature: 36.8, glucose: 145 },
  { timestamp: '2026-09-10T08:00:00Z', heart_rate: 82, spo2: 96, systolic_bp: 138, diastolic_bp: 88, temperature: 36.9, glucose: 162 },
  { timestamp: '2026-09-10T09:00:00Z', heart_rate: 88, spo2: 95, systolic_bp: 142, diastolic_bp: 90, temperature: 37.1, glucose: 178 },
  { timestamp: '2026-09-10T10:00:00Z', heart_rate: 91, spo2: 94, systolic_bp: 148, diastolic_bp: 93, temperature: 37.2, glucose: 192 },
  { timestamp: '2026-09-10T11:00:00Z', heart_rate: 76, spo2: 97, systolic_bp: 132, diastolic_bp: 84, temperature: 37.0, glucose: 155 },
]

export const CURRENT_VITALS = MOCK_VITALS_HISTORY[MOCK_VITALS_HISTORY.length - 1]

export function getVitalStatus(param: string, value: number | null): VitalStatus {
  if (value === null) return 'NORMAL'
  switch (param) {
    case 'heart_rate':
      if (value > 120 || value < 45) return 'CRITICAL'
      if (value > 100 || value < 55) return 'WARNING'
      return 'NORMAL'
    case 'spo2':
      if (value < 88) return 'CRITICAL'
      if (value < 92) return 'WARNING'
      return 'NORMAL'
    case 'systolic_bp':
      if (value >= 180 || value < 80) return 'CRITICAL'
      if (value >= 140 || value < 90) return 'WARNING'
      return 'NORMAL'
    case 'diastolic_bp':
      if (value >= 110) return 'CRITICAL'
      if (value >= 90) return 'WARNING'
      return 'NORMAL'
    case 'temperature':
      if (value >= 39.5 || value < 35) return 'CRITICAL'
      if (value >= 38.5 || value < 36) return 'WARNING'
      return 'NORMAL'
    case 'glucose':
      if (value >= 250 || value < 54) return 'CRITICAL'
      if (value >= 180 || value < 70) return 'WARNING'
      return 'NORMAL'
    default:
      return 'NORMAL'
  }
}
