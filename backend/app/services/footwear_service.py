"""
Pose-guided footwear compositing (v1).

IDM-VTON handles body garments only; it has no notion of feet. This service
adds shoes/slippers as a separate 2D compositing step: it localises each foot
from the person silhouette, background-removes the shoe image, and warps it
onto the feet. Designed for straight-on, full-body standing photos.

No GPU and no heavy pose dependency — feet are found from the rembg person
mask (feet are the two lowest silhouette lobes). MediaPipe foot landmarks
would improve orientation for angled shots; noted as a future upgrade.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


@dataclass
class Foot:
    cx: int          # centre x of the foot region (px)
    top: int         # y of the ankle / top of the foot band (px)
    bottom: int      # y of the sole (px)
    left: int        # bbox left (px)
    right: int       # bbox right (px)

    @property
    def width(self) -> int:
        return max(1, self.right - self.left)

    @property
    def height(self) -> int:
        return max(1, self.bottom - self.top)


from functools import lru_cache


@lru_cache(maxsize=2)
def _rembg_session(model: str = "u2net_human_seg"):
    """Cache the rembg ONNX session (loading it is ~1-2s otherwise)."""
    from rembg import new_session
    try:
        return new_session(model)
    except Exception:
        return new_session("u2net")


def person_mask(image_path: str) -> np.ndarray:
    """Boolean mask of the largest person region."""
    from rembg import remove
    import io

    with open(image_path, "rb") as f:
        out = remove(f.read(), session=_rembg_session())
    rgba = np.array(Image.open(io.BytesIO(out)).convert("RGBA"))
    mask = rgba[:, :, 3] > 128
    mask = ndimage.binary_fill_holes(mask)
    labeled, n = ndimage.label(mask)
    if n > 1:
        sizes = ndimage.sum(mask, labeled, range(1, n + 1))
        mask = labeled == (int(np.argmax(sizes)) + 1)
    return mask


def shoe_rgba(image_path: str) -> Image.Image:
    """Background-removed, tightly cropped shoe as RGBA with a clean edge."""
    from rembg import remove
    import io

    src = Image.open(image_path)
    # Respect an existing cut-out: many product images already ship as
    # transparent PNGs — don't re-segment those (rembg can only make them worse).
    if src.mode in ("RGBA", "LA") and np.array(src.convert("RGBA"))[:, :, 3].min() < 10:
        rgba = np.array(src.convert("RGBA"))
    else:
        with open(image_path, "rb") as f:
            out = remove(f.read(), session=_rembg_session("u2net"))  # general object model
        rgba = np.array(Image.open(io.BytesIO(out)).convert("RGBA"))

    # Harden the alpha so faint background fringe doesn't composite as a halo:
    # keep only the largest opaque blob, drop near-transparent pixels.
    a = rgba[:, :, 3]
    solid = a > 128
    solid = ndimage.binary_fill_holes(solid)
    labeled, n = ndimage.label(solid)
    if n > 1:
        sizes = ndimage.sum(solid, labeled, range(1, n + 1))
        solid = labeled == (int(np.argmax(sizes)) + 1)
    rgba[:, :, 3] = np.where(solid, a, 0)

    ys, xs = np.where(rgba[:, :, 3] > 40)
    if len(ys) == 0:
        return Image.fromarray(rgba)
    crop = rgba[int(ys.min()):int(ys.max()) + 1, int(xs.min()):int(xs.max()) + 1]

    # Lifestyle photos (someone *wearing* the shoes) segment as a TALL cut-out
    # that includes legs/trousers — that's the "blue sock" artifact. A real shoe
    # is wider than tall, so when the cut-out is clearly portrait, keep only the
    # bottom band (the actual footwear) and re-tighten to it. Clean landscape
    # product shots are left untouched.
    ch, cw = crop.shape[:2]
    if ch > cw * 1.15:
        crop = crop[int(ch * 0.45):]  # bottom ~55% holds the shoes
        aa = crop[:, :, 3]
        yy, xx = np.where(aa > 40)
        if len(yy):
            crop = crop[int(yy.min()):int(yy.max()) + 1, int(xx.min()):int(xx.max()) + 1]

    return Image.fromarray(crop)


def detect_feet(mask: np.ndarray, band_frac: float = 0.16) -> list[Foot]:
    """
    Find up to two feet as the connected lobes in the lowest `band_frac` of the
    person's bounding box. Returns them left-to-right.
    """
    ys, xs = np.where(mask)
    if len(ys) == 0:
        return []
    top, bottom = int(ys.min()), int(ys.max())
    height = bottom - top
    band_top = bottom - int(band_frac * height)

    band = np.zeros_like(mask)
    band[band_top:bottom + 1, :] = mask[band_top:bottom + 1, :]

    labeled, n = ndimage.label(band)
    if n == 0:
        return []

    comps = []
    for lab in range(1, n + 1):
        cys, cxs = np.where(labeled == lab)
        if len(cxs) < 0.0005 * mask.size:  # drop tiny specks
            continue
        comps.append((int(cxs.min()), int(cxs.max()),
                      int(cys.min()), int(cys.max()), len(cxs)))

    if not comps:
        return []

    # Keep the two largest lobes, then order left→right
    comps.sort(key=lambda c: c[4], reverse=True)
    comps = comps[:2]
    comps.sort(key=lambda c: (c[0] + c[1]) / 2)

    feet = []
    for l, r, t, b, _ in comps:
        feet.append(Foot(cx=(l + r) // 2, top=t, bottom=b, left=l, right=r))
    return feet


def composite_footwear(
    person_path: str,
    shoe_path: str,
    output_path: str,
    *,
    width_scale: float = 1.35,
    rotate_out_deg: float = 6.0,
    sole_offset: float = 0.12,
) -> str:
    """
    Place `shoe_path` onto both feet detected in `person_path`.

    width_scale    — shoe width relative to detected foot width
    rotate_out_deg — splay each shoe slightly outward (0 = none)
    sole_offset    — nudge the shoe sole below the detected foot bottom, as a
                     fraction of foot height (aligns the shoe to the ground)
    """
    person = Image.open(person_path).convert("RGBA")
    mask = person_mask(person_path)
    feet = detect_feet(mask)
    if not feet:
        raise ValueError("No feet detected — need a full-body photo showing the feet")

    shoe = shoe_rgba(shoe_path)

    for i, foot in enumerate(feet):
        is_left = i == 0
        target_w = max(8, int(foot.width * width_scale))
        ratio = target_w / shoe.width
        target_h = max(8, int(shoe.height * ratio))
        s = shoe.resize((target_w, target_h), Image.LANCZOS)

        if is_left:
            s = s.transpose(Image.FLIP_LEFT_RIGHT)  # mirror for the left foot
        angle = rotate_out_deg if is_left else -rotate_out_deg
        if angle:
            s = s.rotate(angle, expand=True, resample=Image.BICUBIC)

        # Bottom-anchor: align the shoe's sole to the foot's sole, centred on x.
        x = foot.cx - s.width // 2
        y = int(foot.bottom + sole_offset * foot.height) - s.height
        person.alpha_composite(s, (x, max(0, y)))

    out = person.convert("RGB")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    out.save(output_path, "JPEG", quality=95)
    return output_path
