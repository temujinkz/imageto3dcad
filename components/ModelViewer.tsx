"use client";

import { Suspense, useMemo, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { Bounds, Center, Environment, Html, OrbitControls, useGLTF } from "@react-three/drei";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { useLoader } from "@react-three/fiber";
import { Box, RotateCcw, TriangleAlert } from "lucide-react";
import * as THREE from "three";

type ModelViewerProps = {
  modelUrl?: string;
  mode?: "mesh" | "cad" | "both";
  meshSource?: string | null;
  meshIsHighFidelity?: boolean;
};

const SOURCE_LABELS: Record<string, string> = {
  triposr: "TripoSR",
  luma: "Luma Dream Machine",
  csm: "CSM.ai",
  "tripo-api": "Tripo API",
  meshy: "Meshy.ai"
};

export function ModelViewer({ modelUrl, mode, meshSource, meshIsHighFidelity }: ModelViewerProps) {
  const [resetKey, setResetKey] = useState(0);
  const label = mode === "cad" ? "CAD Preview" : mode === "both" ? "3D Preview" : "Mesh Preview";
  const extension = modelUrl?.split("?")[0].split(".").pop()?.toLowerCase();
  const canPreview = Boolean(modelUrl && ["glb", "gltf", "obj", "stl"].includes(extension ?? ""));

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-blue-700">{label}</p>
          <h2 className="text-2xl font-semibold text-ink">Interactive model viewer</h2>
        </div>
        <button
          type="button"
          onClick={() => setResetKey((value) => value + 1)}
          disabled={!canPreview}
          className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:border-blue-400 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <RotateCcw className="h-4 w-4" aria-hidden />
          Reset Camera
        </button>
      </div>

      {canPreview && meshSource && (
        <div
          className={`mb-4 inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ${
            meshIsHighFidelity ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-800"
          }`}
        >
          {meshIsHighFidelity ? (
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
          ) : (
            <TriangleAlert className="h-3.5 w-3.5" aria-hidden />
          )}
          {meshIsHighFidelity
            ? `3D reconstruction via ${SOURCE_LABELS[meshSource] ?? meshSource}`
            : "Rough estimate only — no 3D reconstruction API configured, showing a flat fallback shape"}
        </div>
      )}

      <div className="h-[460px] overflow-hidden rounded-lg border border-slate-200 bg-slate-100">
        {canPreview && modelUrl ? (
          <Canvas key={resetKey} camera={{ position: [2.8, 2.2, 3.4], fov: 42 }} dpr={[1, 2]}>
            <color attach="background" args={["#eef2f7"]} />
            <ambientLight intensity={0.9} />
            <directionalLight position={[4, 6, 5]} intensity={1.8} />
            <Suspense fallback={<LoaderFallback />}>
              <Bounds fit clip observe margin={1.25}>
                <Center>
                  <Model url={modelUrl} extension={extension ?? ""} />
                </Center>
              </Bounds>
              <Environment preset="city" />
            </Suspense>
            <gridHelper args={[6, 24, "#94a3b8", "#cbd5e1"]} position={[0, -0.02, 0]} />
            <OrbitControls makeDefault enableDamping />
          </Canvas>
        ) : (
          <div className="flex h-full flex-col items-center justify-center px-6 text-center">
            <Box className="mb-3 h-10 w-10 text-slate-400" aria-hidden />
            <p className="text-lg font-semibold text-ink">No preview model yet</p>
            <p className="mt-2 max-w-md text-sm leading-6 text-slate-600">
              Generate a mesh or CAD draft. GLB, OBJ, and STL previews render here when the backend returns a model URL.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}

function Model({ url, extension }: { url: string; extension: string }) {
  if (extension === "glb" || extension === "gltf") {
    return <GltfModel url={url} />;
  }

  if (extension === "obj") {
    return <ObjModel url={url} />;
  }

  if (extension === "stl") {
    return <StlModel url={url} />;
  }

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
    () => new THREE.MeshStandardMaterial({ color: "#94a3b8", roughness: 0.72, metalness: 0.08 }),
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
