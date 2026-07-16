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
    ) -> dict:
        if category not in CATEGORIES:
            raise AppError(
                f"Invalid category. Use one of: {', '.join(sorted(CATEGORIES))}",
                code="VALIDATION_ERROR",
                status_code=400,
            )

        item_id = str(uuid4())
        directory = self._settings.storage_root / "wardrobe"
        directory.mkdir(parents=True, exist_ok=True)
        rel_path = f"wardrobe/{item_id}.{extension}"
        (self._settings.storage_root / rel_path).write_bytes(image_bytes)

        with SessionLocal() as db:
            item = WardrobeItemModel(
                id=item_id,
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

    def list_items(self, category: str | None = None) -> list[dict]:
        with SessionLocal() as db:
            q = db.query(WardrobeItemModel)
            if category:
                q = q.filter(WardrobeItemModel.category == category)
            items = q.order_by(WardrobeItemModel.created_at.desc()).all()
            return [self._item_dict(i) for i in items]

    def delete_item(self, item_id: str) -> None:
        with SessionLocal() as db:
            item = db.get(WardrobeItemModel, item_id)
            if item is None:
                raise NotFoundError(f"Item not found: {item_id}")
            # best-effort file cleanup
            try:
                (self._settings.storage_root / item.image_path).unlink(missing_ok=True)
            except OSError:
                pass
            db.delete(item)
            db.commit()

    # ── Outfits ────────────────────────────────────────────
    def create_outfit(self, *, name: str | None, item_ids: list[str]) -> dict:
        if not item_ids:
            raise AppError("An outfit needs at least one item", code="VALIDATION_ERROR", status_code=400)
        with SessionLocal() as db:
            found = db.query(WardrobeItemModel).filter(WardrobeItemModel.id.in_(item_ids)).count()
            if found != len(set(item_ids)):
                raise AppError("One or more items don't exist", code="VALIDATION_ERROR", status_code=400)
            outfit = OutfitModel(
                id=str(uuid4()),
                name=name,
                item_ids=item_ids,
                created_at=datetime.now(UTC),
            )
            db.add(outfit)
            db.commit()
            db.refresh(outfit)
            return self._outfit_dict(db, outfit)

    def list_outfits(self) -> list[dict]:
        with SessionLocal() as db:
            outfits = db.query(OutfitModel).order_by(OutfitModel.created_at.desc()).all()
            return [self._outfit_dict(db, o) for o in outfits]

    def delete_outfit(self, outfit_id: str) -> None:
        with SessionLocal() as db:
            outfit = db.get(OutfitModel, outfit_id)
            if outfit is None:
                raise NotFoundError(f"Outfit not found: {outfit_id}")
            db.delete(outfit)
            db.commit()

    # ── Serialization ──────────────────────────────────────
    def _url(self, rel_path: str) -> str:
        return f"{self._settings.public_base_url.rstrip('/')}/files/{rel_path}"

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
