import json
from pathlib import Path
from sqlalchemy import (
    create_engine, Column, String, Integer, DateTime, Text, JSON,
    UniqueConstraint, Enum as SQLEnum,
)
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
    garment_upload_id = Column(String, nullable=True)
    garment_category = Column(String, nullable=False)
    job_type = Column(String, nullable=False, default="tryon")
    
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


class WardrobeItemModel(Base):
    __tablename__ = "wardrobe_items"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=True)
    category = Column(String, nullable=False)  # tops|bottoms|footwear|outerwear|accessory
    color = Column(String, nullable=True)
    brand = Column(String, nullable=True)
    image_path = Column(String, nullable=False)  # relative to storage root
    created_at = Column(DateTime(timezone=True), nullable=True)


class OutfitModel(Base):
    __tablename__ = "outfits"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=True)
    item_ids = Column(JSON, default=list)  # ordered wardrobe item ids
    created_at = Column(DateTime(timezone=True), nullable=True)


class PostModel(Base):
    """A shared 'fit check' — an outfit photo the community can vote on."""
    __tablename__ = "feed_posts"

    id = Column(String, primary_key=True, index=True)
    device_id = Column(String, nullable=False, index=True)  # poster (no accounts yet)
    display_name = Column(String, nullable=True)
    image_path = Column(String, nullable=False)
    caption = Column(Text, nullable=True)
    fire_count = Column(Integer, default=0, nullable=False)   # 🔥 yes
    cold_count = Column(Integer, default=0, nullable=False)   # 🥶 no
    comment_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=True)


class VoteModel(Base):
    __tablename__ = "feed_votes"
    __table_args__ = (UniqueConstraint("post_id", "device_id", name="uq_vote_post_device"),)

    id = Column(String, primary_key=True)
    post_id = Column(String, nullable=False, index=True)
    device_id = Column(String, nullable=False, index=True)
    value = Column(String, nullable=False)  # "fire" | "cold"
    created_at = Column(DateTime(timezone=True), nullable=True)


class CommentModel(Base):
    __tablename__ = "feed_comments"

    id = Column(String, primary_key=True)
    post_id = Column(String, nullable=False, index=True)
    device_id = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=True)


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
