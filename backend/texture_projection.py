import numpy as np
from pathlib import Path
import trimesh
from PIL import Image


def project_texture_onto_mesh(
    obj_path: str,
    image_path: str,
    output_glb_path: str,
    alpha_mask_path: str = None,
) -> str:
    import numpy as np
    from pathlib import Path
    import trimesh
    from PIL import Image

    print(f"Loading mesh from {obj_path}...")
    mesh = trimesh.load(obj_path, process=False)

    if isinstance(mesh, trimesh.Scene):
        geometries = list(mesh.geometry.values())
        mesh = max(geometries, key=lambda g: len(g.faces))
        print(f"Extracted largest geometry")

    print(f"Mesh: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")

    # Remove floating fragments
    try:
        components = mesh.split(only_watertight=False)
        if len(components) > 1:
            mesh = max(components, key=lambda c: len(c.faces))
            print(f"Kept main component: {len(mesh.faces)} faces")
    except Exception as e:
        print(f"Component split skipped: {e}")

    # Smooth mesh surface
    try:
        import trimesh.smoothing as smoothing
        smoothing.filter_laplacian(mesh, iterations=2)
        print("Mesh smoothed")
    except Exception as e:
        print(f"Smoothing skipped: {e}")

    # Rotate to face forward
    rotation_y180 = trimesh.transformations.rotation_matrix(
        np.pi, [0, 1, 0]
    )
    mesh.apply_transform(rotation_y180)

    # Load image
    print(f"Loading texture image...")
    img = Image.open(image_path).convert("RGBA")
    img_w, img_h = img.size
    img_rgba = np.array(img, dtype=np.float32) / 255.0
    img_rgb = img_rgba[:, :, :3]
    img_alpha = img_rgba[:, :, 3]

    # Build a mask of valid (non-white, non-background) pixels
    # A pixel is "valid" if it is not nearly white AND has alpha > 0.5
    white_threshold = 0.90
    is_white = np.all(img_rgb > white_threshold, axis=2)
    is_opaque = img_alpha > 0.5
    valid_mask = is_opaque & ~is_white  # True = person pixel

    print(f"Valid person pixels: {valid_mask.sum()} of {img_w * img_h}")

    # Get bounding box of valid (person) pixels only
    valid_rows = np.where(valid_mask.any(axis=1))[0]
    valid_cols = np.where(valid_mask.any(axis=0))[0]

    if len(valid_rows) == 0 or len(valid_cols) == 0:
        print("WARNING: No valid pixels found, using full image")
        row_min, row_max = 0, img_h - 1
        col_min, col_max = 0, img_w - 1
    else:
        row_min, row_max = valid_rows[0], valid_rows[-1]
        col_min, col_max = valid_cols[0], valid_cols[-1]

    person_h = row_max - row_min + 1
    person_w = col_max - col_min + 1
    print(f"Person bounding box: {person_w}x{person_h} pixels")

    # Get vertices
    vertices = mesh.vertices.copy()
    v_min = vertices.min(axis=0)
    v_max = vertices.max(axis=0)
    v_range = v_max - v_min
    v_range[v_range == 0] = 1

    # Project vertices onto image using the person bounding box
    # This ensures we only sample from the person region
    x_norm = (vertices[:, 0] - v_min[0]) / v_range[0]  # 0-1
    y_norm = (vertices[:, 1] - v_min[1]) / v_range[1]  # 0-1

    # Map to person bounding box pixels with small padding
    padding = 0.03
    px = (col_min + (x_norm * (1 - 2*padding) + padding) * person_w)
    px = np.clip(px.astype(int), col_min, col_max)

    # Y is flipped in image coordinates
    py = (row_max - (y_norm * (1 - 2*padding) + padding) * person_h)
    py = np.clip(py.astype(int), row_min, row_max)

    # Sample colors
    print("Sampling vertex colors from person region...")
    vertex_colors = img_rgb[py, px].copy()  # Shape: (N, 3)
    sampled_valid = valid_mask[py, px]  # True where we hit person

    # For vertices that sampled from white/background pixels:
    # find their nearest valid neighbor
    invalid_count = (~sampled_valid).sum()
    if invalid_count > 0:
        print(f"Fixing {invalid_count} vertices that sampled background...")

        # Get all valid pixel coordinates
        valid_ys, valid_xs = np.where(valid_mask)

        if len(valid_ys) > 0:
            from scipy.spatial import cKDTree
            valid_coords = np.column_stack([valid_xs, valid_ys])
            tree = cKDTree(valid_coords)

            # For each invalid vertex, find nearest valid pixel
            invalid_idx = np.where(~sampled_valid)[0]
            query_coords = np.column_stack([
                px[invalid_idx], py[invalid_idx]
            ])
            _, nn_idx = tree.query(query_coords, k=1)
            nearest_xs = valid_xs[nn_idx]
            nearest_ys = valid_ys[nn_idx]
            vertex_colors[invalid_idx] = img_rgb[nearest_ys, nearest_xs]
            print(f"Fixed {invalid_count} vertices using nearest neighbor")

    # Darken back-facing vertices (we only have front photo)
    z_median = np.median(vertices[:, 2])
    back_mask = vertices[:, 2] < (z_median - v_range[2] * 0.1)
    if back_mask.any():
        # Use average front color darkened for back
        front_avg = vertex_colors[~back_mask].mean(axis=0)
        back_blend = 0.4  # How much to darken back
        vertex_colors[back_mask] = (
            vertex_colors[back_mask] * (1 - back_blend) +
            front_avg * back_blend * 0.5
        )
        print(f"Darkened {back_mask.sum()} back-facing vertices")

    # Smooth vertex colors to reduce sampling noise (vectorized version)
    try:
        print("Vectorized smoothing vertex colors...")
        from scipy import sparse
        edges = mesh.edges
        n_vertices = len(vertices)

        # Build adjacency matrix (excluding self loops)
        row_n = np.concatenate([edges[:, 0], edges[:, 1]])
        col_n = np.concatenate([edges[:, 1], edges[:, 0]])
        data_n = np.ones(len(row_n), dtype=np.float32)
        adj_neighbors = sparse.coo_matrix((data_n, (row_n, col_n)), shape=(n_vertices, n_vertices)).tocsr()

        # Degrees (number of neighbors)
        degrees = np.array(adj_neighbors.sum(axis=1)).flatten()

        # For vertices with 0 neighbors, avoid division by zero
        has_neighbors = degrees > 0
        inv_degrees = np.zeros(n_vertices, dtype=np.float32)
        inv_degrees[has_neighbors] = 1.0 / degrees[has_neighbors]
        inv_deg_mat = sparse.diags(inv_degrees)

        # Normalized neighbors average operator: inv_deg_mat * adj_neighbors
        neighbors_avg_op = inv_deg_mat.dot(adj_neighbors)

        smoothed = vertex_colors.copy()
        for _ in range(3):
            neighbors_avg = neighbors_avg_op.dot(smoothed)
            new_smoothed = smoothed * 0.4 + neighbors_avg * 0.6
            # Keep original colors for isolated vertices
            new_smoothed[~has_neighbors] = smoothed[~has_neighbors]
            smoothed = new_smoothed
        vertex_colors = smoothed
        print("Color smoothing done")
    except Exception as e:
        print(f"Color smoothing skipped: {e}")

    # Convert to RGBA uint8. Samples are sRGB photo pixels; glTF COLOR_0 is
    # linear, so convert (matches _srgb_to_linear_u8 in pifuhd_server.py).
    srgb = np.clip(vertex_colors, 0.0, 1.0)
    linear = np.where(
        srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4
    )
    colors_uint8 = np.clip(linear * 255 + 0.5, 0, 255).astype(np.uint8)
    alpha_channel = np.full((len(vertices), 1), 255, dtype=np.uint8)
    vertex_colors_rgba = np.hstack([colors_uint8, alpha_channel])

    # Apply to mesh
    mesh.visual = trimesh.visual.ColorVisuals(
        mesh=mesh,
        vertex_colors=vertex_colors_rgba,
    )

    # Export
    out_path = Path(output_glb_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(str(out_path))

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"Exported textured GLB: {size_mb:.2f} MB at {out_path}")
    return str(out_path)


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
