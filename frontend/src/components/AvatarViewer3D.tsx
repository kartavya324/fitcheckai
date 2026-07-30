import { useRef, useEffect, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { Loader2, Pause, RotateCw, ImageOff } from "lucide-react";

interface AvatarViewer3DProps {
  glbUrl: string;
  height?: number;
  /** Start with auto-rotation on. Users can always toggle it in the viewer. */
  autoRotate?: boolean;
}

export function AvatarViewer3D({
  glbUrl,
  height = 500,
  autoRotate = false,
}: AvatarViewer3DProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadPct, setLoadPct] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rotating, setRotating] = useState(autoRotate);

  useEffect(() => {
    const container = mountRef.current
    if (!container) return

    setLoading(true)
    setLoadPct(null)
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
    // Spec-correct pipeline: GLB vertex colors are exported LINEAR by the
    // backend (sRGB→linear at export), so the default sRGB output encodes
    // them back to photo-faithful values on screen.
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.toneMapping = THREE.NoToneMapping
    container.appendChild(renderer.domElement)

    // Studio-style lighting: soft hemisphere base + key/fill/rim.
    // Total front irradiance ≈ π so a Lambert surface reflects its albedo
    // (i.e. the avatar on screen matches the photo's brightness).
    const hemi = new THREE.HemisphereLight(0xffffff, 0xb1a99e, 2.0)
    scene.add(hemi)

    const frontKey = new THREE.DirectionalLight(0xffffff, 1.6)
    frontKey.position.set(1.5, 3, 4)
    scene.add(frontKey)

    const leftFill = new THREE.DirectionalLight(0xffffff, 0.7)
    leftFill.position.set(-3, 1, 2)
    scene.add(leftFill)

    const rimLight = new THREE.DirectionalLight(0xffffff, 0.5)
    rimLight.position.set(0, 2, -4)
    scene.add(rimLight)

    // Soft contact shadow: radial-gradient disc under the avatar grounds it
    // without the cost of real shadow mapping.
    const shadowCanvas = document.createElement('canvas')
    shadowCanvas.width = shadowCanvas.height = 256
    const sctx = shadowCanvas.getContext('2d')!
    const grad = sctx.createRadialGradient(128, 128, 8, 128, 128, 128)
    grad.addColorStop(0, 'rgba(0,0,0,0.32)')
    grad.addColorStop(0.55, 'rgba(0,0,0,0.12)')
    grad.addColorStop(1, 'rgba(0,0,0,0)')
    sctx.fillStyle = grad
    sctx.fillRect(0, 0, 256, 256)
    const shadowTex = new THREE.CanvasTexture(shadowCanvas)
    const shadowMesh = new THREE.Mesh(
      new THREE.PlaneGeometry(1.6, 1.6),
      new THREE.MeshBasicMaterial({
        map: shadowTex,
        transparent: true,
        depthWrite: false,
      }),
    )
    shadowMesh.rotation.x = -Math.PI / 2
    shadowMesh.position.y = 0.005
    scene.add(shadowMesh)

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.05
    controls.autoRotate = autoRotate
    controls.autoRotateSpeed = 1.2
    // Stop spinning as soon as the user grabs the model
    controls.addEventListener('start', () => {
      if (controls.autoRotate) {
        controls.autoRotate = false
        setRotating(false)
      }
    })
    controlsRef.current = controls
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

        // Fix materials for PIFuHD output, which stores colour as a
        // COLOR_0 vertex attribute. Only force vertexColors when the
        // geometry actually has that attribute — forcing it on a mesh
        // without one makes WebGL feed (0,0,0) and renders solid black
        // (e.g. the textured stub avatar).
        let isPifuhdAvatar = false
        model.traverse((child) => {
          if (!(child as THREE.Mesh).isMesh) return
          const mesh = child as THREE.Mesh
          const hasVertexColors = !!mesh.geometry.getAttribute('color')

          if (!hasVertexColors) return // keep original textured material
          isPifuhdAvatar = true

          // PIFuHD GLBs ship without normals (keeps files ~40% smaller);
          // lit materials need them, so compute here — fast even at 40k verts.
          if (!mesh.geometry.getAttribute('normal')) {
            mesh.geometry.computeVertexNormals()
          }

          const fixMaterial = () => {
            // MeshLambertMaterial renders vertex colors more accurately
            // than MeshStandard for this type of reconstruction output
            return new THREE.MeshLambertMaterial({
              vertexColors: true,
              // White base color so vertex colors show at full value
              color: new THREE.Color(1, 1, 1),
            })
          }

          if (Array.isArray(mesh.material)) {
            mesh.material = mesh.material.map(fixMaterial)
          } else {
            mesh.material = fixMaterial()
          }
        })

        // Guard: a real avatar is a PIFuHD reconstruction and always carries
        // COLOR_0 vertex colors. Anything without them (a stray stub/soldier
        // GLB, a wrong file) is NOT a valid avatar — refuse to render it and
        // surface a failure instead of showing a random 3D model.
        if (!isPifuhdAvatar) {
          console.error('GLB is not a valid avatar (no vertex colors)')
          setError('Failed to load avatar')
          setLoading(false)
          return
        }

        // PIFuHD exports face -Z while the camera sits at +Z; turn the
        // avatar so users greet its front, not its back.
        model.rotation.y = Math.PI

        scene.add(model)
        setLoading(false)
      },
      (xhr) => {
        // Download progress — total is 0 when the server streams without
        // Content-Length (e.g. gzip), so only show a % when it's known.
        if (xhr.total > 0) {
          setLoadPct(Math.min(100, Math.round((xhr.loaded / xhr.total) * 100)))
        }
      },
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
      controlsRef.current = null
      renderer.dispose()
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement)
      }
    }
  }, [glbUrl, height, autoRotate]);

  const toggleRotate = () => {
    const controls = controlsRef.current;
    if (!controls) return;
    controls.autoRotate = !controls.autoRotate;
    setRotating(controls.autoRotate);
  };

  return (
    <div className="relative w-full">
      <div
        ref={mountRef}
        className="w-full overflow-hidden rounded-2xl border border-border"
        style={{ height }}
      />

      {!loading && !error && (
        <button
          type="button"
          onClick={toggleRotate}
          title={rotating ? "Stop rotation" : "Auto-rotate"}
          className="absolute right-3 top-3 flex items-center gap-1.5 rounded-full border border-border bg-background/80 px-3 py-1.5 text-xs font-medium text-foreground shadow-sm backdrop-blur transition-colors hover:bg-background"
        >
          {rotating ? (
            <>
              <Pause className="h-3.5 w-3.5" /> Stop
            </>
          ) : (
            <>
              <RotateCw className="h-3.5 w-3.5" /> Rotate
            </>
          )}
        </button>
      )}

      {loading && (
        <div
          className="absolute inset-0 flex items-center justify-center rounded-2xl bg-background/80"
          style={{ height }}
        >
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              {loadPct !== null ? `Loading 3D model… ${loadPct}%` : "Loading 3D model…"}
            </p>
          </div>
        </div>
      )}

      {error && (
        <div
          className="absolute inset-0 flex items-center justify-center rounded-2xl border border-border bg-muted/30"
          style={{ height }}
        >
          <div className="flex flex-col items-center gap-2 px-6 text-center">
            <ImageOff className="h-8 w-8 text-muted-foreground" />
            <p className="text-sm font-medium text-foreground">{error}</p>
            <p className="text-xs text-muted-foreground">
              Try regenerating your avatar.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
