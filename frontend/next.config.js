/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: [], // add problematic ESM packages here if needed
  images: {
    domains: ['localhost', 'via.placeholder.com'],
  },
  async rewrites() {
    // Only used when mocking is off – proxy to real backend
    if (process.env.NEXT_PUBLIC_USE_REAL_API === 'true') {
      return [
        {
          source: '/api/:path*',
          destination: `${process.env.NEXT_PUBLIC_API_URL}/:path*`,
        },
      ];
    }
    return [];
  },
};

module.exports = nextConfig;