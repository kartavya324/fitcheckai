import { useRef, useEffect, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { Loader2 } from "lucide-react";

interface AvatarViewer3DProps {
  glbUrl: string;
  height?: number;
  autoRotate?: boolean;
}

export function AvatarViewer3D({
  glbUrl,
  height = 500,
  autoRotate = true,
}: AvatarViewer3DProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    setLoading(true);
    setError(null);

    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf5f5f0);

    // Camera
    const width = container.clientWidth;
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    camera.position.set(0, 1.2, 2.5);

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(width, height);
    renderer.shadowMap.enabled = true;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(renderer.domElement);

    // Lighting
    const ambient = new THREE.AmbientLight(0xffffff, 1.2);
    scene.add(ambient);

    const frontLight = new THREE.DirectionalLight(0xffffff, 2.0);
    frontLight.position.set(0, 2, 4);
    frontLight.castShadow = true;
    scene.add(frontLight);

    const leftLight = new THREE.DirectionalLight(0xffffff, 0.8);
    leftLight.position.set(-3, 2, 1);
    scene.add(leftLight);

    const rightLight = new THREE.DirectionalLight(0xffffff, 0.8);
    rightLight.position.set(3, 2, 1);
    scene.add(rightLight);

    const topLight = new THREE.DirectionalLight(0xffffff, 0.5);
    topLight.position.set(0, 5, 0);
    scene.add(topLight);

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.autoRotate = autoRotate;
    controls.autoRotateSpeed = 1.5;
    controls.enableZoom = true;
    controls.minDistance = 1;
    controls.maxDistance = 8;
    controls.target.set(0, 0.8, 0);

    // Load .glb
    const loader = new GLTFLoader();
    loader.load(
      glbUrl,
      (gltf) => {
        const model = gltf.scene;
        const box = new THREE.Box3().setFromObject(model);
        const centre = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        model.position.sub(centre);
        model.position.y += size.y / 2;
        const maxDim = Math.max(size.x, size.y, size.z);
        const scale = 2.0 / maxDim;
        model.scale.setScalar(scale);
        model.traverse((child) => {
          if (child instanceof THREE.Mesh) {
            if (child.material) {
              const mat = child.material as THREE.MeshStandardMaterial;
              mat.needsUpdate = true;
              // Boost vertex color visibility
              if (mat.vertexColors) {
                mat.color = new THREE.Color(1, 1, 1);
              }
            }
          }
        });
        scene.add(model);
        setLoading(false);
      },
      undefined,
      (err) => {
        console.error("GLB load error:", err);
        setError("Failed to load 3D model");
        setLoading(false);
      },
    );

    // Animation
    let animId: number;
    function animate() {
      animId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    }
    animate();

    // Resize
    function onResize() {
      const w = container.clientWidth;
      camera.aspect = w / height;
      camera.updateProjectionMatrix();
      renderer.setSize(w, height);
    }
    window.addEventListener("resize", onResize);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", onResize);
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [glbUrl, height, autoRotate]);

  return (
    <div className="relative w-full">
      <div
        ref={mountRef}
        className="w-full overflow-hidden rounded-2xl border border-border"
        style={{ height }}
      />

      {loading && (
        <div
          className="absolute inset-0 flex items-center justify-center rounded-2xl bg-background/80"
          style={{ height }}
        >
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">Loading 3D model…</p>
          </div>
        </div>
      )}

      {error && (
        <div
          className="absolute inset-0 flex items-center justify-center rounded-2xl bg-background"
          style={{ height }}
        >
          <p className="text-sm text-destructive">{error}</p>
        </div>
      )}
    </div>
  );
}
