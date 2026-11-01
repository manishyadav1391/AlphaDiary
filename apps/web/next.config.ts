import type { NextConfig } from "next";

/**
 * `/api/*` is proxied to the FastAPI container rather than called directly.
 *
 * The session cookie is HttpOnly and, in production, Secure. Same-origin is
 * what lets the browser send it at all; a cross-site call to the API host
 * would drop it. This mirrors the Caddy configuration in SRS 11.1, so local
 * development and the deployed stack behave the same way.
 */
const API_ORIGIN = process.env.API_ORIGIN ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // A self-contained server bundle, so the production image carries no
  // node_modules and runs as a non-root user.
  output: "standalone",
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_ORIGIN}/api/:path*` }];
  },
};

export default nextConfig;
