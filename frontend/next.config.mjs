/** @type {import('next').NextConfig} */

// Derive the backend origin from NEXT_PUBLIC_API_URL so that Next.js image
// optimization works for both local dev and any production deployment without
// requiring manual updates to this file.
const _apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
let _backendProtocol = "http";
let _backendHostname = "localhost";
let _backendPort = "8000";
try {
  const _parsed = new URL(_apiUrl.replace(/\/api\/?$/, ""));
  _backendProtocol = _parsed.protocol.replace(":", "");
  _backendHostname = _parsed.hostname;
  _backendPort = _parsed.port;
} catch (_) {
  // fall back to defaults above
}

const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: _backendProtocol,
        hostname: _backendHostname,
        ...(_backendPort !== "" ? { port: _backendPort } : {}),
        pathname: "/media/**",
      },
    ],
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
