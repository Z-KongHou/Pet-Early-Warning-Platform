import type { NextConfig } from "next";

const aiServiceUrl = process.env.AI_SERVICE_URL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  transpilePackages: ["ezuikit-js"],
  async rewrites() {
    return [
      {
        source: "/api/rag/:path*",
        destination: `${aiServiceUrl}/api/rag/:path*`,
      },
    ];
  },
};

export default nextConfig;
