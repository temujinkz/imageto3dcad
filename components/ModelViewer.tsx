"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { Bounds, Center, Html, OrbitControls, useGLTF } from "@react-three/drei";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { useLoader } from "@react-three/fiber";
import { Box, RotateCcw, Sparkles } from "lucide-react";
import * as THREE from "three";
import { BouncingLogo } from "@/components/BouncingLogo";

type ModelViewerProps = {
  modelUrl?: string;
  fullModelUrl?: string;
  meshIsHighFidelity?: boolean;
  warnings?: string[];
  busy?: boolean;
  busyLabel?: string;
};

// A single, minimal status line for low-fidelity results so users know why
// quality is low and how to improve it. No badge, no long explanation.
function qualityNote(warnings?: string[]): string | null {
  if (!warnings?.length) return null;
  const credit = warnings.find((w) => /credit|insufficient|top up|quota|balance/i.test(w));
  if (credit) {
    return "Offline estimate. The cloud 3D provider is out of credits; add credits for a photoreal mesh.";
  }
  const local = warnings.find((w) => /silhouette|offline|no 3D API|stylized/i.test(w));
  if (local) {
    return "Offline estimate. Add a provider key for photoreal geometry.";
  }
  return null;
}

export function ModelViewer({ modelUrl, fullModelUrl, meshIsHighFidelity, warnings, busy, busyLabel }: ModelViewerProps) {
  const [resetKey, setResetKey] = useState(0);
  const [fullReady, setFullReady] = useState(false);
  const extension = modelUrl?.split("?")[0].split(".").pop()?.toLowerCase();
  const canPreview = Boolean(modelUrl && ["glb", "gltf", "obj", "stl"].includes(extension ?? ""));
  const note = meshIsHighFidelity ? null : qualityNote(warnings);
  // A distinct full-res URL means we're showing the fast proxy first and
  // upgrading to the textured mesh in the background.
  const hasUpgrade = Boolean(fullModelUrl && fullModelUrl !== modelUrl);
  const refining = hasUpgrade && !fullReady && canPreview;

  useEffect(() => {
    setFullReady(false);
  }, [modelUrl, fullModelUrl]);

  const handleFullLoaded = useCallback(() => setFullReady(true), []);

  return (
    <section className="rounded-card border border-line bg-card p-4 shadow-card sm:p-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">3D preview</h2>
        <button
          type="button"
          onClick={() => setResetKey((value) => value + 1)}
          disabled={!canPreview}
          className="group inline-flex items-center gap-1.5 rounded-full border border-line bg-card px-3 py-1.5 text-xs font-medium text-muted transition duration-200 hover:border-accent/40 hover:text-ink disabled:opacity-40"
        >
          <RotateCcw className="h-3.5 w-3.5 transition-transform duration-500 group-hover:-rotate-180" aria-hidden />
          Reset view
        </button>
      </div>

      {canPreview && note && <p className="mb-3 text-xs leading-5 text-muted">{note}</p>}

      <div className="relative h-[480px] touch-none overflow-hidden rounded-[14px] border border-line bg-bone">
        {canPreview && modelUrl ? (
          <Canvas
            key={`${modelUrl}-${resetKey}`}
            camera={{ position: [2.8, 2.2, 3.4], fov: 45, near: 0.01, far: 1000 }}
            dpr={[1, 1.75]}
            gl={{ antialias: true, powerPreference: "high-performance", toneMapping: THREE.NeutralToneMapping }}
            performance={{ min: 0.5 }}
          >
            <color attach="background" args={["#f4f2ec"]} />
            {/* Studio-style lighting replaces the old network-fetched HDR
                environment: much faster to start, works offline, and lights
                textured/vertex-colored meshes cleanly. */}
            <hemisphereLight args={["#ffffff", "#c8c2b4", 1.1]} />
            <ambientLight intensity={0.55} />
            <directionalLight position={[5, 8, 6]} intensity={2.1} castShadow={false} />
            <directionalLight position={[-6, 3, -4]} intensity={0.7} />
            <Suspense fallback={<LoaderFallback />}>
              <Bounds fit observe margin={1.2}>
                <Center>
                  <Model
                    url={modelUrl}
                    fullUrl={hasUpgrade ? fullModelUrl : undefined}
                    extension={extension ?? ""}
                    onFullLoaded={handleFullLoaded}
                  />
                </Center>
              </Bounds>
            </Suspense>
            <gridHelper args={[6, 24, "#d8d3c8", "#e7e3d9"]} position={[0, -0.02, 0]} />
            <OrbitControls
              makeDefault
              enableDamping
              dampingFactor={0.08}
              enableRotate
              enableZoom
              enablePan
              minPolarAngle={0}
              maxPolarAngle={Math.PI}
            />
          </Canvas>
        ) : busy ? (
          <>
            <BouncingLogo size={64} />
            <div className="relative z-10 flex h-full flex-col items-center justify-center px-6 text-center">
              <p className="text-base font-semibold text-ink">{busyLabel ?? "Working on it"}</p>
              <p className="mt-1.5 text-sm text-muted">The 3D and CAD steps take a little while. Hang tight.</p>
            </div>
          </>
        ) : (
          <div className="flex h-full flex-col items-center justify-center px-6 text-center">
            <Box className="mb-3 h-9 w-9 text-muted/60" aria-hidden />
            <p className="text-base font-semibold text-ink">Your model shows up here</p>
            <p className="mt-1.5 max-w-sm text-sm leading-6 text-muted">
              Add some photos above and make a model. Once it&apos;s ready you can spin it around and download it.
            </p>
          </div>
        )}

        {refining && (
          <div className="pointer-events-none absolute bottom-3 right-3 z-10 inline-flex items-center gap-1.5 rounded-full bg-ink/85 px-3 py-1.5 text-xs font-medium text-white shadow-lg backdrop-blur">
            <Sparkles className="h-3.5 w-3.5 animate-pulse" aria-hidden />
            Refining full detail…
          </div>
        )}
      </div>
    </section>
  );
}

function Model({
  url,
  fullUrl,
  extension,
  onFullLoaded
}: {
  url: string;
  fullUrl?: string;
  extension: string;
  onFullLoaded?: () => void;
}) {
  if (extension === "glb" || extension === "gltf")
    return <GltfProgressive proxyUrl={url} fullUrl={fullUrl} onFullLoaded={onFullLoaded} />;
  if (extension === "obj") return <ObjModel url={url} />;
  if (extension === "stl") return <StlModel url={url} />;
  return null;
}

// Turn on per-vertex colors when a mesh carries a COLOR_0 attribute (Hunyuan3D
// and the local silhouette engine both bake color into vertices) and make every
// material render both sides so reconstructed shells are never see-through.
function enrichObject(root: THREE.Object3D) {
  root.traverse((child) => {
    const mesh = child as THREE.Mesh;
    if (!mesh.isMesh) return;
    const geometry = mesh.geometry as THREE.BufferGeometry | undefined;
    if (geometry && !geometry.attributes.normal) {
      geometry.computeVertexNormals();
    }
    const hasVertexColors = Boolean(geometry?.attributes?.color);
    const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    materials.forEach((material) => {
      const std = material as THREE.MeshStandardMaterial;
      if (!std) return;
      std.side = THREE.DoubleSide;
      if (hasVertexColors) std.vertexColors = true;
      const map = std.map as THREE.Texture | null;
      if (map) map.colorSpace = THREE.SRGBColorSpace;
      // Only tame shininess on untextured reconstructions; when a real texture
      // map is present (e.g. Meshy PBR) trust its material values so the
      // regenerated textures render at full clarity.
      if (!map && std.metalness !== undefined && std.metalness > 0.5) std.metalness = 0.1;
      std.needsUpdate = true;
    });
  });
}

// Show the lightweight proxy immediately (Suspense-loaded), then fetch the
// full-resolution textured GLB in the background and swap it in once ready.
function GltfProgressive({
  proxyUrl,
  fullUrl,
  onFullLoaded
}: {
  proxyUrl: string;
  fullUrl?: string;
  onFullLoaded?: () => void;
}) {
  const proxy = useGLTF(proxyUrl);
  const proxyScene = useMemo(() => {
    const clone = proxy.scene.clone(true);
    enrichObject(clone);
    return clone;
  }, [proxy.scene]);

  const [fullScene, setFullScene] = useState<THREE.Object3D | null>(null);

  useEffect(() => {
    setFullScene(null);
    if (!fullUrl) return;
    let cancelled = false;
    const loader = new GLTFLoader();
    loader.load(
      fullUrl,
      (gltf) => {
        if (cancelled) return;
        enrichObject(gltf.scene);
        setFullScene(gltf.scene);
        onFullLoaded?.();
      },
      undefined,
      () => {
        // If the full mesh fails to load, keep showing the proxy.
        if (!cancelled) onFullLoaded?.();
      }
    );
    return () => {
      cancelled = true;
    };
  }, [fullUrl, onFullLoaded]);

  return <primitive object={fullScene ?? proxyScene} />;
}

function ObjModel({ url }: { url: string }) {
  const object = useLoader(OBJLoader, url);
  const prepared = useMemo(() => {
    const clone = object.clone(true);
    clone.traverse((child) => {
      const mesh = child as THREE.Mesh;
      if (!mesh.isMesh) return;
      const geometry = mesh.geometry as THREE.BufferGeometry;
      const hasVertexColors = Boolean(geometry?.attributes?.color);
      mesh.material = new THREE.MeshStandardMaterial({
        color: hasVertexColors ? "#ffffff" : "#b8b2a4",
        vertexColors: hasVertexColors,
        roughness: 0.65,
        metalness: 0.05,
        side: THREE.DoubleSide
      });
    });
    return clone;
  }, [object]);
  return <primitive object={prepared} />;
}

function StlModel({ url }: { url: string }) {
  const geometry = useLoader(STLLoader, url);
  const hasVertexColors = Boolean(geometry.attributes?.color);
  const material = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: hasVertexColors ? "#ffffff" : "#a8a294",
        vertexColors: hasVertexColors,
        roughness: 0.68,
        metalness: 0.08,
        side: THREE.DoubleSide
      }),
    [hasVertexColors]
  );
  return <mesh geometry={geometry} material={material} rotation={[-Math.PI / 2, 0, 0]} />;
}

function LoaderFallback() {
  return (
    <Html center>
      <div className="rounded-md bg-ink/90 px-3 py-1.5 text-sm font-medium text-white shadow-lg">Loading model...</div>
    </Html>
  );
}
