import json
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    create_engine, Column, String, Integer, Float, Boolean, DateTime,
    ForeignKey, Text, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from core.config import settings

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    asi_sender_addr = Column(String(128), unique=True, index=True, nullable=True)
    role = Column(String(32), default="patient")  # "patient", "caregiver"
    display_name = Column(String(128), default="User")
    tz = Column(String(64), default="UTC")
    channel = Column(String(32), default="asi_one")  # "telegram", "sms", "email", "asi_one"
    channel_addr = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Patient(Base):
    __tablename__ = "patients"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    display_name = Column(String(128), nullable=False)
    owner_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    tz = Column(String(64), default="UTC")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    medications = relationship("Medication", back_populates="patient", cascade="all, delete-orphan")
    caregivers = relationship("CaregiverLink", back_populates="patient", cascade="all, delete-orphan")

class CaregiverLink(Base):
    __tablename__ = "caregiver_links"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False)
    caregiver_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    caregiver_name = Column(String(128), default="Family Caregiver")
    caregiver_contact = Column(String(128), default="")
    channel = Column(String(32), default="telegram")
    consent_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    revoked_at = Column(DateTime, nullable=True)
    alert_prefs = Column(Text, default="{}")  # JSON
    
    patient = relationship("Patient", back_populates="caregivers")

class Medication(Base):
    __tablename__ = "medications"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False)
    rxcui = Column(String(32), default="", index=True)
    display_name = Column(String(128), nullable=False)
    strength = Column(String(64), default="")
    form = Column(String(64), default="tablet")
    instructions = Column(String(256), default="")
    qty_on_hand = Column(Integer, default=30)
    qty_per_dose = Column(Integer, default=1)
    last_refill_at = Column(DateTime, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    patient = relationship("Patient", back_populates="medications")
    schedules = relationship("Schedule", back_populates="medication", cascade="all, delete-orphan")
    dose_events = relationship("DoseEvent", back_populates="medication", cascade="all, delete-orphan")

class Schedule(Base):
    __tablename__ = "schedules"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    medication_id = Column(String(36), ForeignKey("medications.id"), nullable=False)
    times = Column(Text, default="[\"08:00\"]")  # JSON list of HH:MM
    days = Column(Text, default="[\"daily\"]")   # JSON list
    with_food = Column(Boolean, default=False)
    start_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    end_date = Column(DateTime, nullable=True)

    medication = relationship("Medication", back_populates="schedules")

class DoseEvent(Base):
    __tablename__ = "dose_events"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    medication_id = Column(String(36), ForeignKey("medications.id"), nullable=False)
    due_at = Column(DateTime, nullable=False, index=True)
    status = Column(String(32), default="pending")  # pending, reminded, taken, skipped, missed
    confirmed_at = Column(DateTime, nullable=True)
    attempts = Column(Integer, default=0)
    source = Column(String(32), default="asi_one")

    medication = relationship("Medication", back_populates="dose_events")
    __table_args__ = (
        Index("idx_med_due", "medication_id", "due_at", unique=True),
    )

class InteractionCheck(Base):
    __tablename__ = "interaction_checks"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=True)
    pair_a = Column(String(128), nullable=False)
    pair_b = Column(String(128), nullable=False)
    finding = Column(Text, default="")
    source_url = Column(String(256), default="")
    checked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class RefillOrder(Base):
    __tablename__ = "refill_orders"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    medication_id = Column(String(36), ForeignKey("medications.id"), nullable=False)
    provider = Column(String(64), nullable=False)
    quote_cents = Column(Integer, nullable=False)
    status = Column(String(32), default="placed")  # pending, placed, cancelled
    payment_ref = Column(String(128), default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class SessionState(Base):
    __tablename__ = "sessions"
    sender_addr = Column(String(128), primary_key=True)
    state_json = Column(Text, default="{}")
    pending_action_json = Column(Text, default="{}")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor = Column(String(128), default="system")
    action = Column(String(128), nullable=False)
    entity = Column(String(128), nullable=False)
    details = Column(Text, default="{}")
    ts = Column(DateTime, default=lambda: datetime.now(timezone.utc))

# Database setup
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    echo=False
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
