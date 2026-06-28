import React, { useEffect, useRef } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

export function AvatarViewer({ url }: { url?: string }) {
  const mountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    // Scene
    const scene = new THREE.Scene();

    // Camera
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
    camera.position.set(0, 1.5, 5); // Position to see the whole avatar

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    mount.appendChild(renderer.domElement);

    // Lights
    const hemiLight = new THREE.HemisphereLight(0xffffff, 0x444444, 2);
    hemiLight.position.set(0, 20, 0);
    scene.add(hemiLight);

    const dirLight = new THREE.DirectionalLight(0xffffff, 1.5);
    dirLight.position.set(3, 10, 10);
    scene.add(dirLight);

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 2.0;
    controls.enablePan = false;
    controls.enableZoom = false; // Lock zoom for cleaner look
    controls.target.set(0, 1, 0); // Focus on avatar's torso

    if (url) {
      // Load Model
      const loader = new GLTFLoader();
      loader.load(
        url,
        (gltf) => {
          const model = gltf.scene;
          model.scale.set(1.6, 1.6, 1.6);
          model.position.set(0, -1.2, 0);
          scene.add(model);
        },
        undefined,
        (error) => {
          console.error("An error occurred loading the GLTF model:", error);
        }
      );
    } else {
      // Build programmatic mannequin
      const mannequin = new THREE.Group();
      const material = new THREE.MeshStandardMaterial({ color: "#d4c5b0", roughness: 0.7, metalness: 0.1 });
      
      // Head
      const head = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.4, 0.35), material);
      head.position.y = 1.7;
      mannequin.add(head);

      // Torso
      const torso = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.7, 0.3), material);
      torso.position.y = 1.15;
      mannequin.add(torso);

      // Arms (T-Pose)
      const leftArm = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.08, 0.7), material);
      leftArm.rotation.z = Math.PI / 2;
      leftArm.position.set(-0.65, 1.35, 0);
      mannequin.add(leftArm);

      const rightArm = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.08, 0.7), material);
      rightArm.rotation.z = Math.PI / 2;
      rightArm.position.set(0.65, 1.35, 0);
      mannequin.add(rightArm);

      // Legs
      const leftLeg = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.1, 0.8), material);
      leftLeg.position.set(-0.15, 0.4, 0);
      mannequin.add(leftLeg);

      const rightLeg = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.1, 0.8), material);
      rightLeg.position.set(0.15, 0.4, 0);
      mannequin.add(rightLeg);

      mannequin.position.set(0, -0.8, 0); // Center in view
      scene.add(mannequin);
    }

    // Animation Loop
    let animationFrameId: number;
    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const handleResize = () => {
      if (!mount) return;
      const width = mount.clientWidth;
      const height = mount.clientHeight;
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    
    window.addEventListener('resize', handleResize);
    handleResize(); // Initial sizing

    // Cleanup
    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationFrameId);
      if (mount && mount.contains(renderer.domElement)) {
        mount.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, [url]);

  return (
    <div 
      ref={mountRef} 
      className="h-full w-full overflow-hidden bg-transparent"
    />
  );
}
