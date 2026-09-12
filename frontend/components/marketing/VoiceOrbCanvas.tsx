"use client";

/**
 * components/marketing/VoiceOrbCanvas.tsx
 * ==========================================
 * The page's signature element (Full_Style_Description.txt's brief:
 * "floating microphone, sound waves, neural network nodes... subtle
 * real-time animation... pulsing microphone, flowing data particles").
 *
 * A wireframe icosahedron "neural voice orb" breathing in place, wrapped in
 * a slow-drifting particle shell — meant to read as "the AI is listening."
 * Built directly with three.js per technologies.txt (no react-three-fiber).
 */
import { useEffect, useRef } from "react";
import * as THREE from "three";

export function VoiceOrbCanvas({ className }: { className?: string }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const width = container.clientWidth;
    const height = container.clientHeight;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    camera.position.z = 6.2;

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // ── Core wireframe orb ──
    const coreGeometry = new THREE.IcosahedronGeometry(1.6, 2);
    const coreMaterial = new THREE.MeshBasicMaterial({
      color: 0x00ff9f,
      wireframe: true,
      transparent: true,
      opacity: 0.55,
    });
    const orb = new THREE.Mesh(coreGeometry, coreMaterial);
    scene.add(orb);

    // ── Soft inner glow ──
    const glowGeometry = new THREE.IcosahedronGeometry(1.52, 1);
    const glowMaterial = new THREE.MeshBasicMaterial({
      color: 0x00ff9f,
      transparent: true,
      opacity: 0.07,
    });
    const glow = new THREE.Mesh(glowGeometry, glowMaterial);
    scene.add(glow);

    // ── Outer particle shell (drifting data points) ──
    const particleCount = 260;
    const positions = new Float32Array(particleCount * 3);
    const speeds = new Float32Array(particleCount);
    for (let i = 0; i < particleCount; i++) {
      const r = 2.4 + Math.random() * 2.6;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(Math.random() * 2 - 1);
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = r * Math.cos(phi);
      speeds[i] = 0.2 + Math.random() * 0.6;
    }
    const particleGeometry = new THREE.BufferGeometry();
    particleGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const particleMaterial = new THREE.PointsMaterial({
      color: 0x4eead0,
      size: 0.028,
      transparent: true,
      opacity: 0.65,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const particles = new THREE.Points(particleGeometry, particleMaterial);
    scene.add(particles);

    let frameId = 0;
    const start = performance.now();

    function animate() {
      const elapsed = (performance.now() - start) / 1000;

      if (!prefersReducedMotion) {
        orb.rotation.y += 0.0016;
        orb.rotation.x += 0.0006;
        particles.rotation.y -= 0.0007;
        particles.rotation.x += 0.0002;
        const pulse = 1 + Math.sin(elapsed * 1.3) * 0.045;
        orb.scale.setScalar(pulse);
        glow.scale.setScalar(pulse);
      }

      renderer.render(scene, camera);
      frameId = requestAnimationFrame(animate);
    }
    animate();

    function handleResize() {
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    }
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      cancelAnimationFrame(frameId);
      coreGeometry.dispose();
      coreMaterial.dispose();
      glowGeometry.dispose();
      glowMaterial.dispose();
      particleGeometry.dispose();
      particleMaterial.dispose();
      renderer.dispose();
      container.removeChild(renderer.domElement);
    };
  }, []);

  return <div ref={containerRef} className={className} aria-hidden="true" />;
}
