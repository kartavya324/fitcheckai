"""
Social Fit-Check feed.

Users post an outfit photo and ask "does this work?"; the community votes 🔥/🥶
and comments. This is the app's namesake and its most social surface.

Identity is device-based for now (a persistent device_id from the client) — there
are no accounts yet. Votes are one-per-device-per-post. Before production this
needs real auth (ownership, abuse limits) and content moderation on uploads.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.config import Settings
from app.core.exceptions import AppError, NotFoundError
from app.db import CommentModel, PostModel, SessionLocal, VoteModel

VOTE_VALUES = {"fire", "cold"}


class FeedService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    # ── Posts ──────────────────────────────────────────────
    def create_post(
        self,
        *,
        device_id: str,
        display_name: str | None,
        image_bytes: bytes,
        extension: str,
        caption: str | None,
    ) -> dict:
        post_id = str(uuid4())
        directory = self._settings.storage_root / "feed"
        directory.mkdir(parents=True, exist_ok=True)
        rel_path = f"feed/{post_id}.{extension}"
        (self._settings.storage_root / rel_path).write_bytes(image_bytes)

        with SessionLocal() as db:
            post = PostModel(
                id=post_id,
                device_id=device_id,
                display_name=(display_name or "").strip()[:40] or None,
                image_path=rel_path,
                caption=(caption or "").strip()[:280] or None,
                fire_count=0,
                cold_count=0,
                comment_count=0,
                created_at=datetime.now(UTC),
            )
            db.add(post)
            db.commit()
            db.refresh(post)
            return self._post_dict(post, device_id)

    def list_feed(self, *, device_id: str, limit: int = 20, offset: int = 0) -> dict:
        with SessionLocal() as db:
            total = db.query(PostModel).count()
            posts = (
                db.query(PostModel)
                .order_by(PostModel.created_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )
            # Resolve this device's vote on each listed post in one query.
            ids = [p.id for p in posts]
            my_votes = {}
            if ids:
                for v in (
                    db.query(VoteModel)
                    .filter(VoteModel.device_id == device_id, VoteModel.post_id.in_(ids))
                    .all()
                ):
                    my_votes[v.post_id] = v.value
            items = [self._post_dict(p, device_id, my_votes.get(p.id)) for p in posts]
            return {"items": items, "total": total, "limit": limit, "offset": offset}

    def delete_post(self, *, post_id: str, device_id: str) -> None:
        with SessionLocal() as db:
            post = db.get(PostModel, post_id)
            if post is None:
                raise NotFoundError(f"Post not found: {post_id}")
            if post.device_id != device_id:
                raise AppError("You can only delete your own post", code="FORBIDDEN", status_code=403)
            try:
                (self._settings.storage_root / post.image_path).unlink(missing_ok=True)
            except OSError:
                pass
            db.query(VoteModel).filter(VoteModel.post_id == post_id).delete()
            db.query(CommentModel).filter(CommentModel.post_id == post_id).delete()
            db.delete(post)
            db.commit()

    # ── Votes ──────────────────────────────────────────────
    def vote(self, *, post_id: str, device_id: str, value: str) -> dict:
        if value not in VOTE_VALUES:
            raise AppError("Vote must be 'fire' or 'cold'", code="VALIDATION_ERROR", status_code=400)
        with SessionLocal() as db:
            post = db.get(PostModel, post_id)
            if post is None:
                raise NotFoundError(f"Post not found: {post_id}")

            existing = (
                db.query(VoteModel)
                .filter(VoteModel.post_id == post_id, VoteModel.device_id == device_id)
                .first()
            )
            my_vote: str | None
            if existing is None:
                db.add(
                    VoteModel(
                        id=str(uuid4()),
                        post_id=post_id,
                        device_id=device_id,
                        value=value,
                        created_at=datetime.now(UTC),
                    )
                )
                _bump(post, value, +1)
                my_vote = value
            elif existing.value == value:
                # Toggle off — remove the vote.
                _bump(post, value, -1)
                db.delete(existing)
                my_vote = None
            else:
                # Switch sides.
                _bump(post, existing.value, -1)
                _bump(post, value, +1)
                existing.value = value
                my_vote = value

            db.commit()
            db.refresh(post)
            return self._post_dict(post, device_id, my_vote)

    # ── Comments ───────────────────────────────────────────
    def add_comment(self, *, post_id: str, device_id: str, display_name: str | None, text: str) -> dict:
        text = (text or "").strip()
        if not text:
            raise AppError("Comment can't be empty", code="VALIDATION_ERROR", status_code=400)
        with SessionLocal() as db:
            post = db.get(PostModel, post_id)
            if post is None:
                raise NotFoundError(f"Post not found: {post_id}")
            comment = CommentModel(
                id=str(uuid4()),
                post_id=post_id,
                device_id=device_id,
                display_name=(display_name or "").strip()[:40] or None,
                text=text[:500],
                created_at=datetime.now(UTC),
            )
            db.add(comment)
            post.comment_count = (post.comment_count or 0) + 1
            db.commit()
            db.refresh(comment)
            return self._comment_dict(comment)

    def list_comments(self, post_id: str) -> dict:
        with SessionLocal() as db:
            comments = (
                db.query(CommentModel)
                .filter(CommentModel.post_id == post_id)
                .order_by(CommentModel.created_at.asc())
                .all()
            )
            return {"items": [self._comment_dict(c) for c in comments]}

    # ── Serialization ──────────────────────────────────────
    def _url(self, rel_path: str) -> str:
        return f"{self._settings.public_base_url.rstrip('/')}/files/{rel_path}"

    def _post_dict(self, post: PostModel, device_id: str, my_vote: str | None = "__unset__") -> dict:
        return {
            "id": post.id,
            "display_name": post.display_name or "Someone",
            "image_url": self._url(post.image_path),
            "caption": post.caption,
            "fire_count": post.fire_count or 0,
            "cold_count": post.cold_count or 0,
            "comment_count": post.comment_count or 0,
            "my_vote": None if my_vote == "__unset__" else my_vote,
            "is_mine": post.device_id == device_id,
            "created_at": post.created_at.isoformat() if post.created_at else None,
        }

    def _comment_dict(self, c: CommentModel) -> dict:
        return {
            "id": c.id,
            "display_name": c.display_name or "Someone",
            "text": c.text,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }


def _bump(post: PostModel, value: str, delta: int) -> None:
    if value == "fire":
        post.fire_count = max(0, (post.fire_count or 0) + delta)
    else:
        post.cold_count = max(0, (post.cold_count or 0) + delta)
