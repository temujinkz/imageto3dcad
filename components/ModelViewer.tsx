"use client";

import { Suspense, useMemo, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { Bounds, Center, Environment, OrbitControls, useGLTF, useProgress } from "@react-three/drei";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { useLoader } from "@react-three/fiber";
import { Box, RotateCcw } from "lucide-react";
import * as THREE from "three";
import type { GenerationMode } from "@/lib/types";

type ModelViewerProps = {
  modelUrl?: string;
  mode?: GenerationMode;
};

export function ModelViewer({ modelUrl, mode }: ModelViewerProps) {
  const [resetKey, setResetKey] = useState(0);
  const label = mode === "cad" ? "CAD Preview" : "Mesh Preview";
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
  const { progress } = useProgress();

  return (
    <mesh>
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial color="#bfdbfe" wireframe opacity={0.45} transparent />
      <HtmlLikeLabel text={`Loading ${Math.round(progress)}%`} />
    </mesh>
  );
}

function HtmlLikeLabel({ text }: { text: string }) {
  const texture = useMemo(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 256;
    canvas.height = 64;
    const context = canvas.getContext("2d");
    if (context) {
      context.fillStyle = "#172033";
      context.font = "24px sans-serif";
      context.textAlign = "center";
      context.fillText(text, 128, 40);
    }
    return new THREE.CanvasTexture(canvas);
  }, [text]);

  return (
    <sprite position={[0, 0.9, 0]} scale={[1.8, 0.45, 1]}>
      <spriteMaterial map={texture} transparent />
    </sprite>
  );
}
