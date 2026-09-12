/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  // livekit-client is browser-only (WebRTC APIs). Marking it as a server
  // external prevents Next.js from bundling or evaluating it in the SSR pass,
  // which stopped the dev server from crashing (exit code 0) after the
  // interview page compiled. A package cannot appear in both lists — the
  // client bundle handles livekit-client's ESM natively via SWC without
  // needing transpilePackages (static imports avoid the async-chunk path
  // that previously caused the webpack chunk-loading error).
  serverExternalPackages: ["livekit-client", "@livekit/protocol"],
  // Linting is handled exclusively by Biome (npm run lint / npm run check) —
  // ESLint is intentionally not part of this project.
  eslint: {
    ignoreDuringBuilds: true,
  },
  experimental: {
    optimizePackageImports: ["lucide-react", "recharts"],
  },
  images: {
    remotePatterns: [
      { protocol: "http", hostname: "localhost" },
      { protocol: "https", hostname: "**" },
    ],
  },
};

export default nextConfig;
