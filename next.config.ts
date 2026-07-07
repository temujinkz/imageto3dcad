import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  turbopack: {
    root: process.cwd()
  },
  // Lets `npm run build` produce a static ./out export that the FastAPI
  // backend can serve directly from a single port; see app/main.py.
  output: "export",
  images: {
    unoptimized: true
  }
};

export default nextConfig;
