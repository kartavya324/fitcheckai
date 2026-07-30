"""
Wardrobe / Outfit builder.

Users save garments (their own clothes or items they've tried) into a digital
closet, then combine them into named outfits. Persistence is SQLite (via the
shared Base); images live under storage/wardrobe/.

NOTE: items/outfits are currently global (no auth yet) — the same limitation the
whole app has. Scope by user_id once accounts land.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.config import Settings
from app.core.exceptions import AppError, NotFoundError
from app.db import OutfitModel, SessionLocal, WardrobeItemModel
from app.services.storage_backend import get_storage_backend, content_type_for

CATEGORIES = {"tops", "bottoms", "footwear", "outerwear", "accessory"}


class WardrobeService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    # ── Items ──────────────────────────────────────────────
    def add_item(
        self,
        *,
        image_bytes: bytes,
        extension: str,
        category: str,
        name: str | None = None,
        color: str | None = None,
        brand: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        if category not in CATEGORIES:
            raise AppError(
                f"Invalid category. Use one of: {', '.join(sorted(CATEGORIES))}",
                code="VALIDATION_ERROR",
                status_code=400,
            )

        item_id = str(uuid4())
        rel_path = f"wardrobe/{item_id}.{extension}"
        get_storage_backend().save(rel_path, image_bytes, content_type_for(rel_path))

        with SessionLocal() as db:
            item = WardrobeItemModel(
                id=item_id,
                user_id=user_id,
                name=name,
                category=category,
                color=color,
                brand=brand,
                image_path=rel_path,
                created_at=datetime.now(UTC),
            )
            db.add(item)
            db.commit()
            db.refresh(item)
            return self._item_dict(item)

    def list_items(
        self, category: str | None = None, user_id: str | None = None
    ) -> list[dict]:
        with SessionLocal() as db:
            q = db.query(WardrobeItemModel)
            if category:
                q = q.filter(WardrobeItemModel.category == category)
            # Ownership: a logged-in user sees their own items; anonymous
            # requests see only legacy unowned (null) items.
            q = q.filter(WardrobeItemModel.user_id == user_id)
            items = q.order_by(WardrobeItemModel.created_at.desc()).all()
            return [self._item_dict(i) for i in items]

    def delete_item(self, item_id: str, user_id: str | None = None) -> None:
        with SessionLocal() as db:
            item = db.get(WardrobeItemModel, item_id)
            if item is None or item.user_id != user_id:
                raise NotFoundError(f"Item not found: {item_id}")
            # best-effort file cleanup (local disk or remote object)
            try:
                get_storage_backend().delete(item.image_path)
            except Exception:
                pass
            db.delete(item)
            db.commit()

    # ── Outfits ────────────────────────────────────────────
    def create_outfit(
        self, *, name: str | None, item_ids: list[str], user_id: str | None = None
    ) -> dict:
        if not item_ids:
            raise AppError("An outfit needs at least one item", code="VALIDATION_ERROR", status_code=400)
        with SessionLocal() as db:
            # Only the caller's own items may go into their outfit
            found = db.query(WardrobeItemModel).filter(
                WardrobeItemModel.id.in_(item_ids),
                WardrobeItemModel.user_id == user_id,
            ).count()
            if found != len(set(item_ids)):
                raise AppError("One or more items don't exist", code="VALIDATION_ERROR", status_code=400)
            outfit = OutfitModel(
                id=str(uuid4()),
                user_id=user_id,
                name=name,
                item_ids=item_ids,
                created_at=datetime.now(UTC),
            )
            db.add(outfit)
            db.commit()
            db.refresh(outfit)
            return self._outfit_dict(db, outfit)

    def list_outfits(self, user_id: str | None = None) -> list[dict]:
        with SessionLocal() as db:
            outfits = (
                db.query(OutfitModel)
                .filter(OutfitModel.user_id == user_id)
                .order_by(OutfitModel.created_at.desc())
                .all()
            )
            return [self._outfit_dict(db, o) for o in outfits]

    def delete_outfit(self, outfit_id: str, user_id: str | None = None) -> None:
        with SessionLocal() as db:
            outfit = db.get(OutfitModel, outfit_id)
            if outfit is None or outfit.user_id != user_id:
                raise NotFoundError(f"Outfit not found: {outfit_id}")
            db.delete(outfit)
            db.commit()

    # ── Serialization ──────────────────────────────────────
    def _url(self, rel_path: str) -> str:
        return get_storage_backend().url(rel_path)

    def _item_dict(self, item: WardrobeItemModel) -> dict:
        return {
            "id": item.id,
            "name": item.name,
            "category": item.category,
            "color": item.color,
            "brand": item.brand,
            "image_url": self._url(item.image_path),
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }

    def _outfit_dict(self, db, outfit: OutfitModel) -> dict:
        ids = outfit.item_ids or []
        by_id = {
            i.id: i
            for i in db.query(WardrobeItemModel).filter(WardrobeItemModel.id.in_(ids)).all()
        }
        items = [self._item_dict(by_id[i]) for i in ids if i in by_id]  # preserve order
        return {
            "id": outfit.id,
            "name": outfit.name,
            "items": items,
            "created_at": outfit.created_at.isoformat() if outfit.created_at else None,
        }
