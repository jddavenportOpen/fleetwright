/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  async rewrites() {
    const bridgeUrl = process.env.BRIDGE_URL || 'http://localhost:8787'
    return [
      {
        source: '/api/bridge/:path*',
        destination: `${bridgeUrl}/:path*`,
      },
    ]
  },
}
export default nextConfig
