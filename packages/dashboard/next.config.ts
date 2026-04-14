import type { NextConfig } from "next";

const nextConfig: NextConfig = {
	output: "export", // Static export for bundling into the Python package
	distDir: "dist",
	images: {
		unoptimized: true, // Required for static export
	},
};

export default nextConfig;
