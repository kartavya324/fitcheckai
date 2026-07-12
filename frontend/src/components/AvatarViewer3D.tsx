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

    // Strong ambient so vertex colors are always visible
    const ambient = new THREE.AmbientLight(0xffffff, 2.5)
    scene.add(ambient)
    
    // Front key light
    const frontLight = new THREE.DirectionalLight(0xffffff, 1.5)
    frontLight.position.set(0, 3, 5)
    scene.add(frontLight)
    
    // Left fill
    const leftLight = new THREE.DirectionalLight(0xffffff, 0.8)
    leftLight.position.set(-4, 2, 2)
    scene.add(leftLight)
    
    // Right fill  
    const rightLight = new THREE.DirectionalLight(0xffffff, 0.8)
    rightLight.position.set(4, 2, 2)
    scene.add(rightLight)
    
    // Back light to prevent completely dark back
    const backLight = new THREE.DirectionalLight(0xffffff, 0.5)
    backLight.position.set(0, 2, -5)
    scene.add(backLight)
    
    // Bottom fill to prevent dark feet
    const bottomLight = new THREE.DirectionalLight(0xffffff, 0.3)
    bottomLight.position.set(0, -3, 2)
    scene.add(bottomLight)

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
        const model = gltf.scene
        
        // Centre and scale the model
        const box = new THREE.Box3().setFromObject(model)
        const centre = box.getCenter(new THREE.Vector3())
        const size = box.getSize(new THREE.Vector3())
        model.position.sub(centre)
        model.position.y += size.y / 2
        const maxDim = Math.max(size.x, size.y, size.z)
        const scale = 2.2 / maxDim
        model.scale.setScalar(scale)
        
        // Fix materials to show vertex colors correctly
        model.traverse((child) => {
          if ((child as THREE.Mesh).isMesh) {
            const mesh = child as THREE.Mesh
            const materials = Array.isArray(mesh.material)
              ? mesh.material
              : [mesh.material]
            
            materials.forEach((mat) => {
              if (mat instanceof THREE.MeshStandardMaterial) {
                // Enable vertex colors
                mat.vertexColors = true
                // White base so vertex colors show at full brightness
                mat.color = new THREE.Color(1, 1, 1)
                // Reduce metalness/roughness for better color display
                mat.metalness = 0
                mat.roughness = 0.8
                mat.needsUpdate = true
              } else {
                // Replace any non-standard material with one 
                // that supports vertex colors
                const newMat = new THREE.MeshStandardMaterial({
                  vertexColors: true,
                  color: new THREE.Color(1, 1, 1),
                  metalness: 0,
                  roughness: 0.8,
                })
                if (Array.isArray(mesh.material)) {
                  const idx = mesh.material.indexOf(mat)
                  if (idx >= 0) mesh.material[idx] = newMat
                } else {
                  mesh.material = newMat
                }
              }
            })
            mesh.castShadow = true
            mesh.receiveShadow = true
          }
        })
        
        scene.add(model)
        setLoading(false)
      },
      (progress) => {
        // Optional loading progress
        console.log('Loading:', 
          Math.round(progress.loaded / progress.total * 100) + '%')
      },
      (err) => {
        console.error('GLB load error:', err)
        setError('Failed to load 3D model')
        setLoading(false)
      },
    )

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
