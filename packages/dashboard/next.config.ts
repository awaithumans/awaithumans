import type { NextConfig } from "next";

// Static export is only used when explicitly building for production bundling
// into the Python package. In dev mode, we need dynamic routes (like /api/discover)
// to work, which isn't compatible with `output: "export"`.
const isStaticExport = process.env.AWAITHUMANS_STATIC_EXPORT === "true";

const nextConfig: NextConfig = {
	...(isStaticExport
		? {
				output: "export",
				distDir: "dist",
				images: { unoptimized: true },
			}
		: {}),
};

export default nextConfig;
