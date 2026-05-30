import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "static.bbqorder.co.kr",
        pathname: "/**",
      },
    ],
  },
};

export default nextConfig;
