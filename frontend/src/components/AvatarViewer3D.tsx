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
    const container = mountRef.current
    if (!container) return

    setLoading(true)
    setError(null)

    const width = container.clientWidth
    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0xf5f5f0)

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100)
    camera.position.set(0, 1.0, 2.8)

    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(window.devicePixelRatio)
    renderer.setSize(width, height)
    renderer.shadowMap.enabled = false
    // CRITICAL: use NoColorSpace so vertex colors are not 
    // gamma corrected (which causes the pale/washed look)
    renderer.outputColorSpace = THREE.LinearSRGBColorSpace
    renderer.toneMapping = THREE.NoToneMapping
    container.appendChild(renderer.domElement)

    // Balanced lighting — not too bright (causes washout)
    // not too dark
    const ambient = new THREE.AmbientLight(0xffffff, 1.8)
    scene.add(ambient)

    const frontKey = new THREE.DirectionalLight(0xffffff, 1.2)
    frontKey.position.set(0, 2, 4)
    scene.add(frontKey)

    const leftFill = new THREE.DirectionalLight(0xffffff, 0.6)
    leftFill.position.set(-3, 1, 2)
    scene.add(leftFill)

    const rightFill = new THREE.DirectionalLight(0xffffff, 0.6)
    rightFill.position.set(3, 1, 2)
    scene.add(rightFill)

    const backLight = new THREE.DirectionalLight(0xffffff, 0.3)
    backLight.position.set(0, 1, -4)
    scene.add(backLight)

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.05
    controls.autoRotate = autoRotate
    controls.autoRotateSpeed = 1.2
    controls.enableZoom = true
    controls.minDistance = 0.8
    controls.maxDistance = 6
    controls.target.set(0, 0.7, 0)
    controls.update()

    const loader = new GLTFLoader()
    loader.load(
      glbUrl,
      (gltf) => {
        const model = gltf.scene

        // Centre and scale
        const box = new THREE.Box3().setFromObject(model)
        const centre = box.getCenter(new THREE.Vector3())
        const size = box.getSize(new THREE.Vector3())
        model.position.sub(centre)
        model.position.y += size.y / 2
        const maxDim = Math.max(size.x, size.y, size.z)
        model.scale.setScalar(2.0 / maxDim)

        // Fix all materials to show vertex colors properly
        model.traverse((child) => {
          if (!(child as THREE.Mesh).isMesh) return
          const mesh = child as THREE.Mesh

          const fixMaterial = (mat: THREE.Material) => {
            // Replace with MeshLambertMaterial which renders
            // vertex colors more accurately than MeshStandard
            // for this type of reconstruction output
            const newMat = new THREE.MeshLambertMaterial({
              vertexColors: true,
              // White base color so vertex colors show at full value
              color: new THREE.Color(1, 1, 1),
            })
            return newMat
          }

          if (Array.isArray(mesh.material)) {
            mesh.material = mesh.material.map(fixMaterial)
          } else {
            mesh.material = fixMaterial(mesh.material)
          }
        })

        scene.add(model)
        setLoading(false)
      },
      undefined,
      (err) => {
        console.error('GLB load error:', err)
        setError('Failed to load 3D model')
        setLoading(false)
      }
    )

    let animId: number
    const animate = () => {
      animId = requestAnimationFrame(animate)
      controls.update()
      renderer.render(scene, camera)
    }
    animate()

    const onResize = () => {
      const w = container.clientWidth
      camera.aspect = w / height
      camera.updateProjectionMatrix()
      renderer.setSize(w, height)
    }
    window.addEventListener('resize', onResize)

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', onResize)
      renderer.dispose()
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement)
      }
    }
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
