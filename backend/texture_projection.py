import numpy as np
from pathlib import Path
import trimesh
from PIL import Image


def project_texture_onto_mesh(
    obj_path: str,
    image_path: str,
    output_glb_path: str,
) -> str:
    """
    Project photo colors onto 3D mesh as vertex colors.
    
    PIFuHD reconstructs geometry but not texture.
    This function takes the original photo and projects
    each pixel's color onto the nearest visible mesh vertex
    using orthographic projection from the front view.
    
    Args:
        obj_path: Path to PIFuHD output .obj file
        image_path: Path to original person photo (with white bg)
        output_glb_path: Where to save the textured .glb
    
    Returns:
        Path to output .glb file
    """
    print(f"Loading mesh from {obj_path}...")
    
    # Load mesh
    mesh = trimesh.load(obj_path, process=False)
    if isinstance(mesh, trimesh.Scene):
        geometries = list(mesh.geometry.values())
        mesh = max(geometries, key=lambda g: len(g.faces))
    
    print(f"Mesh: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")
    
    # Remove floating fragments — keep only largest component
    try:
        components = mesh.split(only_watertight=False)
        if len(components) > 1:
            mesh = max(components, key=lambda c: len(c.faces))
            print(f"Kept largest component: {len(mesh.faces)} faces")
    except Exception as e:
        print(f"Component split skipped: {e}")
    
    # Smooth the mesh to reduce chunky appearance
    # Laplacian smoothing passes
    try:
        import trimesh.smoothing as smoothing
        print("Smoothing mesh...")
        smoothing.filter_laplacian(mesh, iterations=3)
        print("Smoothing complete")
    except Exception as e:
        print(f"Smoothing skipped: {e}")
    
    # Rotate mesh to face +Z (PIFuHD outputs facing -Z)
    rotation_y180 = trimesh.transformations.rotation_matrix(
        np.pi, [0, 1, 0]
    )
    mesh.apply_transform(rotation_y180)
    
    # Load and resize image
    print(f"Loading image from {image_path}...")
    img = Image.open(image_path).convert("RGB")
    img_width, img_height = img.size
    img_array = np.array(img, dtype=np.float32) / 255.0
    
    # Get vertices
    vertices = mesh.vertices.copy()
    
    # Normalize vertices to [-1, 1] range for projection
    v_min = vertices.min(axis=0)
    v_max = vertices.max(axis=0)
    v_range = v_max - v_min
    v_range[v_range == 0] = 1  # Avoid division by zero
    
    # Project using front-facing orthographic projection
    # X maps to image width, Y maps to image height (flipped)
    # We use X and Y coordinates of 3D vertices
    x_norm = (vertices[:, 0] - v_min[0]) / v_range[0]  # 0 to 1
    y_norm = (vertices[:, 1] - v_min[1]) / v_range[1]  # 0 to 1
    
    # Convert to pixel coordinates
    # Y is flipped because image Y goes top-to-bottom
    # Add margin to avoid edge effects
    margin = 0.05
    px = ((x_norm * (1 - 2*margin) + margin) * (img_width - 1)).astype(int)
    py = (((1 - y_norm) * (1 - 2*margin) + margin) * (img_height - 1)).astype(int)
    
    # Clamp to image bounds
    px = np.clip(px, 0, img_width - 1)
    py = np.clip(py, 0, img_height - 1)
    
    # Sample colors from image at each vertex position
    print("Projecting colors onto vertices...")
    vertex_colors = img_array[py, px]  # Shape: (N, 3)
    
    # Detect back-facing vertices using Z coordinate
    # Vertices with Z below median are on the back
    z_median = np.median(vertices[:, 2])
    back_mask = vertices[:, 2] < z_median
    
    # For back vertices, use a slightly darker version of 
    # the average color (since we only have front photo)
    avg_color = vertex_colors[~back_mask].mean(axis=0)
    back_color = avg_color * 0.6  # Darker for back
    vertex_colors[back_mask] = back_color
    
    # Smooth vertex colors to reduce noise
    # Average each vertex color with its neighbors
    # (Removed slow Python loop as requested)
    
    # Convert to uint8 with alpha
    colors_uint8 = (vertex_colors * 255).astype(np.uint8)
    alpha = np.full((len(vertices), 1), 255, dtype=np.uint8)
    vertex_colors_rgba = np.hstack([colors_uint8, alpha])
    
    # Apply colors to mesh
    mesh.visual = trimesh.visual.ColorVisuals(
        mesh=mesh,
        vertex_colors=vertex_colors_rgba,
    )
    
    print(f"Applied colors to {len(vertices)} vertices")
    
    # Export as GLB
    output_path = Path(output_glb_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(str(output_path))
    
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Exported textured GLB: {size_mb:.2f} MB")
    
    return str(output_path)


def test_projection(image_path: str):
    """Quick test without running full PIFuHD pipeline."""
    import tempfile
    import os
    
    # Create a simple test mesh (cylinder = rough person shape)
    mesh = trimesh.creation.cylinder(radius=0.3, height=1.8, sections=32)
    
    with tempfile.TemporaryDirectory() as tmp:
        obj_path = os.path.join(tmp, "test.obj")
        mesh.export(obj_path)
        
        output_path = "test_textured.glb"
        project_texture_onto_mesh(obj_path, image_path, output_path)
        
        print(f"Test complete: {output_path}")
        print("Open at: https://gltf-viewer.donmccurdy.com")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        test_projection(sys.argv[1])
    else:
        print("Usage: python texture_projection.py <image_path>")
