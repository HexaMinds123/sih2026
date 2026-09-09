"""Database layer for Patient EHR MCP Server.

Provides dual-storage support:
- MongoDB Atlas (primary, shared with clinical-mcp)
- SQLite (local fallback, patients.db)

server.py never writes raw queries directly; all access is abstracted here.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=False)


class PatientDatabase:
    """Encapsulates all patient data access with MongoDB primary and SQLite fallback."""

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            self.db_path = str(Path(__file__).parent / "patients.db")
        else:
            self.db_path = str(Path(db_path)) if Path(db_path).is_absolute() else str(Path(__file__).parent / db_path)
        self._init_sqlite_schema()

        self.mongo_uri = os.getenv("MONGO_URI")
        self.database_name = os.getenv("MONGO_DATABASE", "clinical_knowledge")
        self._mongo_client: Any = None
        self._mongo_db: Any = None

        if self.mongo_uri:
            try:
                from pymongo import MongoClient

                self._mongo_client = MongoClient(
                    self.mongo_uri,
                    serverSelectionTimeoutMS=5000,
                    minPoolSize=5,
                    maxPoolSize=50,
                )
                self._mongo_client.admin.command("ping")
                self._mongo_db = self._mongo_client[self.database_name]
                self._init_mongo_indexes()
            except Exception:
                self._mongo_db = None

    # =========================================================================
    # Schema Initializations
    # =========================================================================

    def _init_sqlite_schema(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS patients (
                    patient_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    age INTEGER NOT NULL,
                    gender TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS allergies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT NOT NULL,
                    allergy TEXT NOT NULL,
                    severity TEXT DEFAULT 'moderate',
                    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conditions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT NOT NULL,
                    condition TEXT NOT NULL,
                    diagnosed_date TEXT DEFAULT '',
                    status TEXT DEFAULT 'active',
                    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prescriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT NOT NULL,
                    drug TEXT NOT NULL,
                    dosage TEXT NOT NULL,
                    frequency TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    prescribed_date TEXT DEFAULT '',
                    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS emergency_contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    relationship TEXT NOT NULL,
                    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def _init_mongo_indexes(self) -> None:
        if self._mongo_db is None:
            return
        for col_name in ["patients", "allergies", "conditions", "prescriptions", "emergency_contacts"]:
            self._mongo_db[col_name].create_index("patient_id")

    def _get_sqlite_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # =========================================================================
    # Query Operations
    # =========================================================================

    def patient_exists(self, patient_id: str) -> bool:
        """Check if a patient exists."""
        if self._mongo_db is not None:
            return self._mongo_db.patients.count_documents({"patient_id": patient_id}, limit=1) > 0

        conn = self._get_sqlite_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM patients WHERE patient_id = ? LIMIT 1", (patient_id,))
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def get_patient_profile(self, patient_id: str) -> dict[str, Any] | None:
        """Get demographics, allergies, and conditions. Returns None if patient doesn't exist."""
        if not self.patient_exists(patient_id):
            return None

        if self._mongo_db is not None:
            patient = self._mongo_db.patients.find_one({"patient_id": patient_id}, {"_id": 0})
            if not patient:
                return None
            allergies = [
                doc.get("allergy") for doc in self._mongo_db.allergies.find({"patient_id": patient_id}, {"_id": 0})
            ]
            conditions = [
                doc.get("condition") for doc in self._mongo_db.conditions.find({"patient_id": patient_id}, {"_id": 0})
            ]
            return {
                "patient_id": patient["patient_id"],
                "name": patient["name"],
                "age": patient["age"],
                "gender": patient["gender"],
                "allergies": allergies,
                "conditions": conditions,
            }

        conn = self._get_sqlite_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            patient = dict(row)

            cursor.execute("SELECT allergy FROM allergies WHERE patient_id = ?", (patient_id,))
            allergies = [r["allergy"] for r in cursor.fetchall()]

            cursor.execute("SELECT condition FROM conditions WHERE patient_id = ?", (patient_id,))
            conditions = [r["condition"] for r in cursor.fetchall()]

            return {
                **patient,
                "allergies": allergies,
                "conditions": conditions,
            }
        finally:
            conn.close()

    def get_active_prescriptions(self, patient_id: str) -> list[dict[str, Any]] | None:
        """Get all active prescriptions. Returns None if patient doesn't exist."""
        if not self.patient_exists(patient_id):
            return None

        if self._mongo_db is not None:
            docs = list(self._mongo_db.prescriptions.find(
                {"patient_id": patient_id, "active": True},
                {"_id": 0, "drug": 1, "dosage": 1, "frequency": 1, "prescribed_date": 1}
            ))
            return docs

        conn = self._get_sqlite_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT drug, dosage, frequency, prescribed_date FROM prescriptions WHERE patient_id = ? AND active = 1",
                (patient_id,),
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def get_allergies(self, patient_id: str) -> list[str] | None:
        """Get all allergy names for a patient. Returns None if patient doesn't exist."""
        if not self.patient_exists(patient_id):
            return None

        if self._mongo_db is not None:
            docs = list(self._mongo_db.allergies.find({"patient_id": patient_id}, {"_id": 0, "allergy": 1}))
            return [d["allergy"] for d in docs]

        conn = self._get_sqlite_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT allergy FROM allergies WHERE patient_id = ?", (patient_id,))
            return [r["allergy"] for r in cursor.fetchall()]
        finally:
            conn.close()

    def get_medical_conditions(self, patient_id: str) -> list[str] | None:
        """Get all medical condition names for a patient. Returns None if patient doesn't exist."""
        if not self.patient_exists(patient_id):
            return None

        if self._mongo_db is not None:
            docs = list(self._mongo_db.conditions.find({"patient_id": patient_id}, {"_id": 0, "condition": 1}))
            return [d["condition"] for d in docs]

        conn = self._get_sqlite_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT condition FROM conditions WHERE patient_id = ?", (patient_id,))
            return [r["condition"] for r in cursor.fetchall()]
        finally:
            conn.close()

    def get_emergency_contact(self, patient_id: str) -> dict[str, Any] | None:
        """Get primary emergency contact. Returns None if patient doesn't exist."""
        if not self.patient_exists(patient_id):
            return None

        if self._mongo_db is not None:
            doc = self._mongo_db.emergency_contacts.find_one(
                {"patient_id": patient_id},
                {"_id": 0, "name": 1, "phone": 1, "relationship": 1}
            )
            return doc

        conn = self._get_sqlite_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, phone, relationship FROM emergency_contacts WHERE patient_id = ? LIMIT 1",
                (patient_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_all_patient_ids(self) -> list[str]:
        """Get all patient IDs."""
        if self._mongo_db is not None:
            return self._mongo_db.patients.distinct("patient_id")

        conn = self._get_sqlite_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT patient_id FROM patients ORDER BY patient_id")
            return [row["patient_id"] for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_all_patients(self) -> list[dict[str, Any]]:
        """Get complete profiles for all patients."""
        patient_ids = self.get_all_patient_ids()
        profiles = []
        for pid in patient_ids:
            profile = self.get_patient_profile(pid)
            if profile:
                profiles.append(profile)
        return profiles

    # =========================================================================
    # Write Operations
    # =========================================================================

    def clear_all_data(self) -> None:
        """Clear all patient data while strictly preserving clinical collections."""
        if self._mongo_db is not None:
            for col_name in ["patients", "allergies", "conditions", "prescriptions", "emergency_contacts"]:
                self._mongo_db[col_name].delete_many({})

        conn = self._get_sqlite_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM emergency_contacts")
            cursor.execute("DELETE FROM prescriptions")
            cursor.execute("DELETE FROM conditions")
            cursor.execute("DELETE FROM allergies")
            cursor.execute("DELETE FROM patients")
            conn.commit()
        finally:
            conn.close()

    def insert_patient(self, patient_id: str, name: str, age: int, gender: str) -> None:
        """Insert patient demographic record."""
        if self._mongo_db is not None:
            self._mongo_db.patients.replace_one(
                {"patient_id": patient_id},
                {"patient_id": patient_id, "name": name, "age": age, "gender": gender},
                upsert=True,
            )

        conn = self._get_sqlite_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO patients (patient_id, name, age, gender) VALUES (?, ?, ?, ?)",
                (patient_id, name, age, gender),
            )
            conn.commit()
        finally:
            conn.close()

    def insert_allergy(self, patient_id: str, allergy: str, severity: str = "moderate") -> None:
        """Insert allergy record."""
        if self._mongo_db is not None:
            self._mongo_db.allergies.insert_one({
                "patient_id": patient_id,
                "allergy": allergy,
                "severity": severity,
            })

        conn = self._get_sqlite_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO allergies (patient_id, allergy, severity) VALUES (?, ?, ?)",
                (patient_id, allergy, severity),
            )
            conn.commit()
        finally:
            conn.close()

    def insert_condition(self, patient_id: str, condition: str, diagnosed_date: str = "", status: str = "active") -> None:
        """Insert condition record."""
        if self._mongo_db is not None:
            self._mongo_db.conditions.insert_one({
                "patient_id": patient_id,
                "condition": condition,
                "diagnosed_date": diagnosed_date,
                "status": status,
            })

        conn = self._get_sqlite_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO conditions (patient_id, condition, diagnosed_date, status) VALUES (?, ?, ?, ?)",
                (patient_id, condition, diagnosed_date, status),
            )
            conn.commit()
        finally:
            conn.close()

    def insert_prescription(self, patient_id: str, drug: str, dosage: str, frequency: str, active: bool = True, prescribed_date: str = "") -> None:
        """Insert prescription record."""
        if self._mongo_db is not None:
            self._mongo_db.prescriptions.insert_one({
                "patient_id": patient_id,
                "drug": drug,
                "dosage": dosage,
                "frequency": frequency,
                "active": active,
                "prescribed_date": prescribed_date,
            })

        conn = self._get_sqlite_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO prescriptions (patient_id, drug, dosage, frequency, active, prescribed_date) VALUES (?, ?, ?, ?, ?, ?)",
                (patient_id, drug, dosage, frequency, 1 if active else 0, prescribed_date),
            )
            conn.commit()
        finally:
            conn.close()

    def insert_emergency_contact(self, patient_id: str, name: str, phone: str, relationship: str) -> None:
        """Insert emergency contact."""
        if self._mongo_db is not None:
            self._mongo_db.emergency_contacts.replace_one(
                {"patient_id": patient_id},
                {"patient_id": patient_id, "name": name, "phone": phone, "relationship": relationship},
                upsert=True,
            )

        conn = self._get_sqlite_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO emergency_contacts (patient_id, name, phone, relationship) VALUES (?, ?, ?, ?)",
                (patient_id, name, phone, relationship),
            )
            conn.commit()
        finally:
            conn.close()
