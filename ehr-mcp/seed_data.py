"""Seed data script for Patient EHR MCP Server.

Idempotent: wipes existing patient collections in MongoDB Atlas & SQLite,
populates 5 diverse demonstration patients, and indexes their vector embeddings.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

from database import PatientDatabase
from rag import MongoPatientRAGStore, format_patient_document


def seed_demo_patients():
    """Populate 5 diverse demo patients and generate vector embeddings."""
    load_dotenv(Path(__file__).parent / ".env", override=False)

    print("Initializing database connection...")
    db = PatientDatabase("patients.db")

    print("Clearing existing patient data...")
    db.clear_all_data()

    print("Seeding 5 diverse clinical demonstration patients...")

    # Patient 1: Multi-condition (Diabetes + Hypertension)
    print("  -> Seeding P001: John Doe (52M, Diabetes + Hypertension)")
    db.insert_patient("P001", "John Doe", 52, "Male")
    db.insert_allergy("P001", "Penicillin", "severe")
    db.insert_allergy("P001", "Sulfa drugs", "moderate")
    db.insert_condition("P001", "Type 2 Diabetes", "2020-03-15", "active")
    db.insert_condition("P001", "Hypertension", "2018-09-10", "active")
    db.insert_prescription("P001", "Metformin", "500 mg", "Twice daily", active=True, prescribed_date="2020-03-15")
    db.insert_prescription("P001", "Lisinopril", "10 mg", "Once daily", active=True, prescribed_date="2018-09-10")
    db.insert_prescription("P001", "Amlodipine", "5 mg", "Once daily", active=True, prescribed_date="2021-06-01")
    db.insert_emergency_contact("P001", "Jane Doe", "+1-555-0142", "Spouse")

    # Patient 2: Respiratory (Asthma)
    print("  -> Seeding P002: Sarah Jenkins (34F, Asthma)")
    db.insert_patient("P002", "Sarah Jenkins", 34, "Female")
    db.insert_allergy("P002", "Pollen", "mild")
    db.insert_allergy("P002", "Dust mites", "moderate")
    db.insert_condition("P002", "Asthma", "2015-05-20", "active")
    db.insert_prescription("P002", "Albuterol Inhaler", "90 mcg", "2 puffs every 4-6 hours PRN", active=True, prescribed_date="2023-01-15")
    db.insert_prescription("P002", "Budesonide Inhaler", "180 mcg", "1 puff twice daily", active=True, prescribed_date="2023-01-15")
    db.insert_emergency_contact("P002", "Mark Jenkins", "+1-555-0198", "Husband")

    # Patient 3: Cardiac polypharmacy (Warfarin + Aspirin interaction risk)
    print("  -> Seeding P003: Marcus Vance (67M, Cardiac Polypharmacy)")
    db.insert_patient("P003", "Marcus Vance", 67, "Male")
    db.insert_allergy("P003", "Morphine", "severe")
    db.insert_condition("P003", "Atrial Fibrillation", "2019-11-04", "active")
    db.insert_condition("P003", "Deep Vein Thrombosis", "2021-02-18", "active")
    db.insert_prescription("P003", "Warfarin", "5 mg", "Once daily in evening", active=True, prescribed_date="2019-11-04")
    db.insert_prescription("P003", "Aspirin", "81 mg", "Once daily", active=True, prescribed_date="2021-02-18")
    db.insert_prescription("P003", "Atorvastatin", "40 mg", "Once daily at bedtime", active=True, prescribed_date="2019-11-04")
    db.insert_emergency_contact("P003", "Robert Vance", "+1-555-0312", "Son")

    # Patient 4: Renal & Multiple Drug Allergies
    print("  -> Seeding P004: Elena Rostova (48F, Chronic Kidney Disease)")
    db.insert_patient("P004", "Elena Rostova", 48, "Female")
    db.insert_allergy("P004", "Penicillin", "anaphylaxis")
    db.insert_allergy("P004", "Cephalosporins", "severe")
    db.insert_allergy("P004", "Codeine", "moderate")
    db.insert_condition("P004", "Chronic Kidney Disease Stage 3", "2022-08-14", "active")
    db.insert_condition("P004", "Hypertension", "2020-04-12", "active")
    db.insert_prescription("P004", "Losartan", "50 mg", "Once daily", active=True, prescribed_date="2020-04-12")
    db.insert_prescription("P004", "Furosemide", "20 mg", "Once daily in morning", active=True, prescribed_date="2022-08-14")
    db.insert_emergency_contact("P004", "Alexei Rostov", "+1-555-0456", "Brother")

    # Patient 5: Healthy Baseline (No chronic conditions, no active prescriptions)
    print("  -> Seeding P005: David Kim (29M, Healthy Baseline)")
    db.insert_patient("P005", "David Kim", 29, "Male")
    db.insert_emergency_contact("P005", "Hannah Kim", "+1-555-0589", "Sister")

    print("\nGenerating RAG embeddings for all 5 patient medical narratives...")
    rag_store = MongoPatientRAGStore()
    for pid in ["P001", "P002", "P003", "P004", "P005"]:
        narrative = format_patient_document(pid, db)
        count = rag_store.upsert_patient_record(pid, narrative, metadata={"kind": "patient_ehr"})
        print(f"  -> Indexed {pid} ({count} chunk(s)) into patient RAG store")

    print("\nSeeding complete!")
    print("  P001: John Doe (Diabetes, Hypertension; Meds: Metformin, Lisinopril, Amlodipine)")
    print("  P002: Sarah Jenkins (Asthma; Meds: Albuterol, Budesonide)")
    print("  P003: Marcus Vance (Atrial Fib, DVT; Meds: Warfarin, Aspirin [Interaction Risk!])")
    print("  P004: Elena Rostova (CKD, Multi-Allergy; Meds: Losartan, Furosemide)")
    print("  P005: David Kim (Healthy baseline)")


if __name__ == "__main__":
    seed_demo_patients()
