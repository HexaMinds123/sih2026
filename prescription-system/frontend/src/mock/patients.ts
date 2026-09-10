import type { EHRPatient } from '../types/index'

// Mock data matching EHR-MCP seed patients (P001, P002, P003)
// NOTE: This is DEMO DATA — not retrieved from backend in real-time.
export const MOCK_PATIENTS: EHRPatient[] = [
  {
    patient_id: 'P001',
    name: 'Sarah Mitchell',
    age: 52,
    gender: 'Female',
    bloodType: 'B+',
    allergies: ['Penicillin', 'Sulfonamides'],
    conditions: ['Type 2 Diabetes', 'Hypertension', 'Hypothyroidism'],
    emergencyContact: { name: 'James Mitchell', phone: '+1-555-0147', relation: 'Spouse' },
  },
  {
    patient_id: 'P002',
    name: 'Robert Chen',
    age: 67,
    gender: 'Male',
    bloodType: 'O+',
    allergies: ['Latex', 'Codeine'],
    conditions: ['COPD', 'Atrial Fibrillation', 'Osteoarthritis'],
    emergencyContact: { name: 'Linda Chen', phone: '+1-555-0288', relation: 'Daughter' },
  },
  {
    patient_id: 'P003',
    name: 'Marcus Vance',
    age: 74,
    gender: 'Male',
    bloodType: 'A-',
    allergies: ['Aspirin (monitored)', 'NSAIDs'],
    conditions: ['Coronary Artery Disease', 'Heart Failure', 'Chronic Kidney Disease'],
    emergencyContact: { name: 'Diana Vance', phone: '+1-555-0391', relation: 'Wife' },
  },
]

export const ACTIVE_PATIENT = MOCK_PATIENTS[0]
