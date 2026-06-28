import json
from pathlib import Path
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, JSON, Enum as SQLEnum
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import get_settings
from app.models.job import JobStatus

Base = declarative_base()

class JobModel(Base):
    __tablename__ = "jobs"

    job_id = Column(String, primary_key=True, index=True)
    status = Column(SQLEnum(JobStatus), nullable=False)
    progress = Column(Integer, default=0, nullable=False)
    person_upload_id = Column(String, nullable=False)
    garment_upload_id = Column(String, nullable=False)
    garment_category = Column(String, nullable=False)
    
    person_path = Column(String, nullable=True)
    garment_path = Column(String, nullable=True)
    result_path = Column(String, nullable=True)
    stage = Column(String, nullable=True)
    
    metadata_json = Column("metadata", JSON, default=dict)
    
    # Store JobError as JSON dict if present
    error_json = Column("error", JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

def get_engine():
    settings = get_settings()
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    db_path = settings.storage_root / "fitcheck.db"
    return create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False}
    )

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
