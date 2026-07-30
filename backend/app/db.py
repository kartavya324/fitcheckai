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

class UserModel(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    email = Column(String, nullable=False, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)


class JobModel(Base):
    __tablename__ = "jobs"

    # Owner (nullable during the accounts migration; new rows always set it)
    user_id = Column(String, index=True, nullable=True)

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
    user_id = Column(String, index=True, nullable=True)
    name = Column(String, nullable=True)
    category = Column(String, nullable=False)  # tops|bottoms|footwear|outerwear|accessory
    color = Column(String, nullable=True)
    brand = Column(String, nullable=True)
    image_path = Column(String, nullable=False)  # relative to storage root
    created_at = Column(DateTime(timezone=True), nullable=True)


class OutfitModel(Base):
    __tablename__ = "outfits"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=True)
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


def get_database_url() -> str:
    """Resolve the DB URL: explicit DATABASE_URL (Postgres in prod), else a
    local SQLite file under storage_root (dev default)."""
    settings = get_settings()
    if settings.database_url:
        return settings.database_url
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    db_path = settings.storage_root / "fitcheck.db"
    return f"sqlite:///{db_path}"


def get_engine():
    url = get_database_url()
    # check_same_thread is a SQLite-only arg; passing it to Postgres errors.
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    # pool_pre_ping avoids stale-connection errors on managed Postgres.
    kwargs = {"connect_args": connect_args}
    if not url.startswith("sqlite"):
        kwargs["pool_pre_ping"] = True
    return create_engine(url, **kwargs)

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema() -> None:
    """Lightweight forward-migration for SQLite: create_all() makes new tables
    (e.g. `users`) but never ADDS columns to existing ones. This adds the
    `user_id` ownership columns to pre-accounts tables if they're missing, so
    existing dev databases keep working without a manual wipe. Phase 2 replaces
    this with Alembic migrations."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    wanted = {
        "jobs": "user_id",
        "wardrobe_items": "user_id",
        "outfits": "user_id",
    }
    with engine.begin() as conn:
        existing_tables = set(inspector.get_table_names())
        for table, column in wanted.items():
            if table not in existing_tables:
                continue
            cols = {c["name"] for c in inspector.get_columns(table)}
            if column not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} VARCHAR"))
