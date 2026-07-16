"""
Personal color analysis ("what colours suit you").

Samples skin tone from the face, derives undertone (warm/cool/neutral) and depth
(light/deep) via CIELAB, maps to a color season, and returns a flattering palette
plus colors to avoid. Reuses the avatar service's Haar face detection.

Undertone/season is an estimate from a single photo (lighting affects it) — the
API surfaces the metrics so it's transparent, like the size advisor.
"""
from __future__ import annotations

import io
import math

import cv2
import numpy as np
from PIL import Image

from app.core.exceptions import AppError

# season -> palette. Colors are (hex, name); curated from standard color theory.
PALETTES: dict[str, dict] = {
    "Spring": {
        "desc": "Warm and light. Clear, fresh colours with a golden warmth flatter you most.",
        "colors": [
            ("#FF6F61", "Coral"), ("#FFB347", "Peach"), ("#FFD700", "Warm gold"),
            ("#9ACD32", "Apple green"), ("#40E0D0", "Turquoise"), ("#FFF4E0", "Ivory"),
            ("#C19A6B", "Camel"), ("#FF7F50", "Warm coral-red"), ("#87CEEB", "Sky blue"),
            ("#F4A460", "Warm sand"),
        ],
        "avoid": [("#000000", "Black"), ("#4B0082", "Deep plum"), ("#708090", "Cool grey")],
    },
    "Autumn": {
        "desc": "Warm and deep. Rich, earthy, muted colours suit you beautifully.",
        "colors": [
            ("#808000", "Olive"), ("#B7410E", "Rust"), ("#E1AD01", "Mustard"),
            ("#E2725B", "Terracotta"), ("#228B22", "Forest green"), ("#FFFDD0", "Cream"),
            ("#C19A6B", "Camel"), ("#008080", "Teal"), ("#CC5500", "Burnt orange"),
            ("#7B3F00", "Chocolate"),
        ],
        "avoid": [("#FF69B4", "Hot pink"), ("#00FFFF", "Icy cyan"), ("#F5F5F5", "Stark white")],
    },
    "Summer": {
        "desc": "Cool and soft. Muted, dusty pastels with a blue base look best on you.",
        "colors": [
            ("#E8A0BF", "Soft rose"), ("#B0C4DE", "Powder blue"), ("#C9A0DC", "Lavender"),
            ("#9CAF88", "Sage"), ("#D8A7B1", "Dusty pink"), ("#708090", "Slate"),
            ("#C4AEAD", "Mauve"), ("#66CDAA", "Soft teal"), ("#CCCCFF", "Periwinkle"),
            ("#A9A9A9", "Cool grey"),
        ],
        "avoid": [("#FF4500", "Orange-red"), ("#FFA500", "Bright orange"), ("#000000", "Harsh black")],
    },
    "Winter": {
        "desc": "Cool and deep. Bold, high-contrast, icy colours make you shine.",
        "colors": [
            ("#E60026", "True red"), ("#009B77", "Emerald"), ("#4169E1", "Royal blue"),
            ("#FF00FF", "Magenta"), ("#000000", "Black"), ("#FFFFFF", "Pure white"),
            ("#B0E0E6", "Ice blue"), ("#C154C1", "Fuchsia"), ("#0047AB", "Cobalt"),
            ("#4B0082", "Deep purple"),
        ],
        "avoid": [("#E1AD01", "Mustard"), ("#B7410E", "Rust"), ("#FFFDD0", "Cream")],
    },
    "Neutral": {
        "desc": "Balanced undertone — versatile, slightly muted colours in medium depth suit you.",
        "colors": [
            ("#1F3A5F", "Navy"), ("#008080", "Teal"), ("#F5F5F0", "Soft white"),
            ("#808080", "Grey"), ("#800020", "Burgundy"), ("#6699CC", "Denim blue"),
            ("#808000", "Olive"), ("#E8A0BF", "Blush"), ("#3B3B3B", "Charcoal"),
            ("#B5651D", "Warm brown"),
        ],
        "avoid": [("#FFFF00", "Neon yellow"), ("#39FF14", "Neon green")],
    },
}


def _cascade():
    try:
        from app.services.avatar_analysis_service import _ensure_cascade_file

        clf = cv2.CascadeClassifier(str(_ensure_cascade_file()))
        if not clf.empty():
            return clf
    except Exception:
        pass
    return cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def _detect_face(img_np: np.ndarray):
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    faces = _cascade().detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    if len(faces) == 0:
        return None
    return max(faces, key=lambda f: int(f[2]) * int(f[3]))


def _sample_skin(img_np: np.ndarray, face) -> np.ndarray | None:
    x, y, w, h = (int(v) for v in face)
    # Cheek/forehead band: central width, rows 45–80% of the face (below the eyes).
    cx0, cx1 = x + int(w * 0.25), x + int(w * 0.75)
    ry0, ry1 = y + int(h * 0.45), y + int(h * 0.80)
    region = img_np[ry0:ry1, cx0:cx1].reshape(-1, 3).astype(np.float32)
    if len(region) < 20:
        return None
    r, g, b = region[:, 0], region[:, 1], region[:, 2]
    skin = region[(r > 60) & (r < 250) & (r >= g) & (g >= b) & (r - b > 8) & (r - b < 130)]
    if len(skin) < 20:
        skin = region
    return np.median(skin, axis=0)


def analyze_colors(image_bytes: bytes) -> dict:
    try:
        img_np = np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
    except Exception as e:
        raise AppError("Could not read the image", code="VALIDATION_ERROR", status_code=400) from e

    face = _detect_face(img_np)
    used_face = face is not None
    if face is None:
        # Fallback to a top-centre band (still gives a rough undertone).
        h, w = img_np.shape[:2]
        face = (w // 4, int(h * 0.05), w // 2, int(h * 0.35))

    skin = _sample_skin(img_np, face)
    if skin is None:
        raise AppError(
            "Couldn't find a clear skin region. Use a well-lit, front-facing photo.",
            code="NO_FACE",
            status_code=400,
        )

    r, g, b = (int(round(v)) for v in skin)
    skin_hex = f"#{r:02X}{g:02X}{b:02X}"

    lab = cv2.cvtColor(np.uint8([[[r, g, b]]]), cv2.COLOR_RGB2LAB)[0, 0].astype(float)
    L = lab[0] * 100.0 / 255.0
    a = lab[1] - 128.0
    bb = lab[2] - 128.0
    hue = math.degrees(math.atan2(bb, a)) if (a or bb) else 0.0
    chroma = math.hypot(a, bb)

    # Plausibility guard: reject near-white/near-black/greyscale samples — that
    # means we sampled background or an over/under-exposed area, not skin.
    if L > 92 or L < 12 or chroma < 6:
        raise AppError(
            "Couldn't find a clear skin region. Use a well-lit, front-facing photo.",
            code="NO_FACE",
            status_code=400,
        )

    depth = "light" if L > 62 else "deep"
    if hue >= 54:
        undertone = "warm"
    elif hue <= 46:
        undertone = "cool"
    else:
        undertone = "neutral"

    season = _season(undertone, depth)
    pal = PALETTES[season]

    return {
        "skin_hex": skin_hex,
        "undertone": undertone,
        "depth": depth,
        "season": season,
        "used_face": used_face,
        "metrics": {"L": round(L, 1), "a": round(a, 1), "b": round(bb, 1), "hue_angle": round(hue, 1)},
        "description": pal["desc"],
        "palette": [{"hex": h, "name": n} for h, n in pal["colors"]],
        "avoid": [{"hex": h, "name": n} for h, n in pal["avoid"]],
        "disclaimer": (
            "Estimated from one photo — lighting and camera affect the result. "
            "Try a couple of natural-light photos for the most reliable read."
        ),
    }


def _season(undertone: str, depth: str) -> str:
    if undertone == "warm":
        return "Spring" if depth == "light" else "Autumn"
    if undertone == "cool":
        return "Summer" if depth == "light" else "Winter"
    return "Neutral"
