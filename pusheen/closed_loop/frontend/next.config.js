/** @type {import('next').NextConfig} */
const nextConfig = {
  // Externalize native modules so they aren't bundled by webpack
  serverExternalPackages: ['better-sqlite3'],
  experimental: {
    serverComponentsExternalPackages: ['better-sqlite3'],
  },
  // Output standalone for better serverless compatibility
  output: 'standalone',
};

module.exports = nextConfig;
