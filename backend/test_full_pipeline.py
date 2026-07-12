r"""
Test the complete avatar pipeline end to end.
Usage: python test_full_pipeline.py path\to\photo.jpg

This tests:
1. Background removal
2. PIFuHD reconstruction  
3. Texture projection
4. GLB export

Saves test_avatar_final.glb — drag to 
https://gltf-viewer.donmccurdy.com to preview
"""
import sys
import os
import tempfile
import shutil
from pathlib import Path

def main(image_path: str):
    print("=" * 60)
    print("FitCheck AI — Full Pipeline Test")
    print("=" * 60)
    
    if not Path(image_path).exists():
        print(f"ERROR: Image not found: {image_path}")
        return
    
    # Add backend to path
    sys.path.insert(0, str(Path(__file__).parent))
    
    from pifuhd_server import (
        remove_background, 
        preprocess_image,
        run_pifuhd,
    )
    from texture_projection import project_texture_onto_mesh
    
    with tempfile.TemporaryDirectory() as tmp:
        print(f"\nStep 1: Preprocessing image...")
        preprocessed = os.path.join(tmp, "preprocessed.jpg")
        preprocess_image(image_path, preprocessed)
        print(f"Done: {preprocessed}")
        
        print(f"\nStep 2: Removing background...")
        bg_removed = os.path.join(tmp, "bg_removed.jpg")
        result = remove_background(preprocessed, bg_removed)
        print(f"Done: {result}")
        
        print(f"\nStep 3: Running PIFuHD (3-6 minutes)...")
        obj_path = run_pifuhd(bg_removed, tmp)
        print(f"Done: {obj_path}")
        
        print(f"\nStep 4: Projecting texture...")
        output_glb = "test_avatar_final.glb"
        project_texture_onto_mesh(
            obj_path=obj_path,
            image_path=bg_removed,
            output_glb_path=output_glb,
        )
        print(f"Done: {output_glb}")
    
    size_mb = Path(output_glb).stat().st_size / (1024*1024)
    print("\n" + "=" * 60)
    print(f"SUCCESS! Avatar generated: {output_glb} ({size_mb:.1f} MB)")
    print("Preview: https://gltf-viewer.donmccurdy.com")
    print("Drag the .glb file into that website")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_full_pipeline.py <image_path>")
        sys.exit(1)
    main(sys.argv[1])
