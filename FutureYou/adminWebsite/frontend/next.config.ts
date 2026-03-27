import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactCompiler: true,
  output: "export",
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
