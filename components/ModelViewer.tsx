"use client";

import { Suspense, useMemo, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { Bounds, Center, Environment, Html, OrbitControls, useGLTF } from "@react-three/drei";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { useLoader } from "@react-three/fiber";
import { Box, Loader2, RotateCcw, Sparkles, TriangleAlert } from "lucide-react";
import * as THREE from "three";

type ModelViewerProps = {
  modelUrl?: string;
  meshSource?: string | null;
  meshIsHighFidelity?: boolean;
  busy?: boolean;
  busyLabel?: string;
};

const SOURCE_LABELS: Record<string, string> = {
  "wavespeed-hunyuan3d": "Hunyuan3D (WaveSpeed)",
  "fal-hunyuan3d": "Hunyuan3D (fal)",
  meshy: "Meshy",
  "tripo-api": "Tripo",
  triposr: "TripoSR",
  luma: "Luma",
  csm: "CSM",
  silhouette: "local silhouette engine",
  mock: "mock"
};

export function ModelViewer({ modelUrl, meshSource, meshIsHighFidelity, busy, busyLabel }: ModelViewerProps) {
  const [resetKey, setResetKey] = useState(0);
  const extension = modelUrl?.split("?")[0].split(".").pop()?.toLowerCase();
  const canPreview = Boolean(modelUrl && ["glb", "gltf", "obj", "stl"].includes(extension ?? ""));

  return (
    <section className="rounded-card border border-line bg-card p-4 shadow-card sm:p-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">3D preview</h2>
        <button
          type="button"
          onClick={() => setResetKey((value) => value + 1)}
          disabled={!canPreview}
          className="inline-flex items-center gap-1.5 rounded-full border border-line bg-card px-3 py-1.5 text-xs font-medium text-muted transition hover:text-ink disabled:opacity-40"
        >
          <RotateCcw className="h-3.5 w-3.5" aria-hidden />
          Reset view
        </button>
      </div>

      {canPreview && meshSource && (
        <div
          className={`mb-3 inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ${
            meshIsHighFidelity ? "bg-emerald-50 text-emerald-700" : "bg-accent/10 text-accent"
          }`}
        >
          {meshIsHighFidelity ? (
            <Sparkles className="h-3.5 w-3.5" aria-hidden />
          ) : (
            <TriangleAlert className="h-3.5 w-3.5" aria-hidden />
          )}
          {meshIsHighFidelity
            ? `Built with ${SOURCE_LABELS[meshSource] ?? meshSource}`
            : `Rough guess from the outline. Add a reconstruction key for a sharper model.`}
        </div>
      )}

      <div className="h-[480px] overflow-hidden rounded-[14px] border border-line bg-bone">
        {canPreview && modelUrl ? (
          <Canvas key={resetKey} camera={{ position: [2.8, 2.2, 3.4], fov: 42 }} dpr={[1, 2]}>
            <color attach="background" args={["#f4f2ec"]} />
            <ambientLight intensity={0.95} />
            <directionalLight position={[4, 6, 5]} intensity={1.7} />
            <Suspense fallback={<LoaderFallback />}>
              <Bounds fit clip observe margin={1.25}>
                <Center>
                  <Model url={modelUrl} extension={extension ?? ""} />
                </Center>
              </Bounds>
              <Environment preset="city" />
            </Suspense>
            <gridHelper args={[6, 24, "#d8d3c8", "#e7e3d9"]} position={[0, -0.02, 0]} />
            <OrbitControls makeDefault enableDamping />
          </Canvas>
        ) : busy ? (
          <div className="flex h-full flex-col items-center justify-center px-6 text-center">
            <Loader2 className="mb-3 h-8 w-8 animate-spin text-accent" aria-hidden />
            <p className="text-base font-semibold text-ink">{busyLabel ?? "Working on it"}</p>
            <p className="mt-1.5 text-sm text-muted">The 3D and CAD steps take a little while. Hang tight.</p>
          </div>
        ) : (
          <div className="flex h-full flex-col items-center justify-center px-6 text-center">
            <Box className="mb-3 h-9 w-9 text-muted/60" aria-hidden />
            <p className="text-base font-semibold text-ink">Your model shows up here</p>
            <p className="mt-1.5 max-w-sm text-sm leading-6 text-muted">
              Add some photos above and make a model. Once it&apos;s ready you can spin it around and download it.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}

function Model({ url, extension }: { url: string; extension: string }) {
  if (extension === "glb" || extension === "gltf") return <GltfModel url={url} />;
  if (extension === "obj") return <ObjModel url={url} />;
  if (extension === "stl") return <StlModel url={url} />;
  return null;
}

function GltfModel({ url }: { url: string }) {
  const gltf = useGLTF(url);
  return <primitive object={gltf.scene} />;
}

function ObjModel({ url }: { url: string }) {
  const object = useLoader(OBJLoader, url);
  return <primitive object={object} />;
}

function StlModel({ url }: { url: string }) {
  const geometry = useLoader(STLLoader, url);
  const material = useMemo(
    () => new THREE.MeshStandardMaterial({ color: "#8b8577", roughness: 0.7, metalness: 0.1 }),
    []
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
