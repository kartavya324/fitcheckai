"""
Quick end-to-end check for the improved PIFuHD avatar pipeline.

Usage:
    1. Start the GPU server:   start_pifuhd_server.bat
    2. In another terminal:    python verify_avatar.py [path\\to\\photo.jpg]

Saves the resulting avatar to  verify_avatar_output.glb  and prints a
colour report so you can confirm the mesh is textured (not grey).
Open the .glb at https://gltf-viewer.donmccurdy.com to inspect it.
"""
import sys
import base64
from pathlib import Path

import httpx

DEFAULT_PHOTO = Path("storage/avatars/uploads")
SERVER = "http://localhost:8090"


def pick_photo() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1]
    # fall back to any stored upload
    for p in DEFAULT_PHOTO.glob("*.jpg"):
        return str(p)
    raise SystemExit("No photo given and none found in storage/avatars/uploads")


def main() -> None:
    photo = pick_photo()
    print(f"Photo: {photo}")

    img_b64 = base64.b64encode(Path(photo).read_bytes()).decode()

    print(f"POST {SERVER}/generate  (this takes ~3-6 min on an RTX 3050)...")
    resp = httpx.post(
        f"{SERVER}/generate",
        json={"image_base64": img_b64},
        timeout=600.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise SystemExit(f"Server error: {data['error']}")

    glb = base64.b64decode(data["glb_base64"])
    out = Path("verify_avatar_output.glb")
    out.write_bytes(glb)
    print(f"Saved {out} ({len(glb)/1_048_576:.2f} MB)")

    # Colour report — proves the mesh is textured, not a grey blob
    try:
        import trimesh
        import numpy as np

        m = trimesh.load(str(out), process=False)
        if isinstance(m, trimesh.Scene):
            m = max(m.geometry.values(), key=lambda g: len(g.faces))
        vc = np.array(m.visual.vertex_colors)[:, :3].astype(float)
        chroma = np.abs(vc - vc.mean(axis=1, keepdims=True)).mean()
        print(f"verts={len(m.vertices)}  meanRGB={vc.mean(0).round(0)}  "
              f"colourfulness(chroma)={chroma:.1f}")
        print("  chroma > 8  => textured (good).  chroma ~ 0 => still grey (bad).")
    except Exception as e:
        print(f"(colour report skipped: {e})")


if __name__ == "__main__":
    main()
