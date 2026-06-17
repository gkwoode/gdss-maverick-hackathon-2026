/** @type {import('next').NextConfig} */

// Derive the production API hostname from NEXT_PUBLIC_API_URL at build time
// so that Next.js Image Optimization accepts media URLs served by the backend.
function getProductionImagePattern() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiUrl) return null;
  try {
    const { protocol, hostname, port } = new URL(apiUrl);
    return {
      protocol: protocol.replace(":", ""),
      hostname,
      ...(port ? { port } : {}),
      pathname: "/media/**",
    };
  } catch {
    return null;
  }
}

const productionImagePattern = getProductionImagePattern();

const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "http",
        hostname: "localhost",
        port: "8000",
        pathname: "/media/**",
      },
      ...(productionImagePattern ? [productionImagePattern] : []),
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
