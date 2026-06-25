import type { NextConfig } from "next";

/**
 * Static-export config for GitHub Pages.
 *
 * The dashboard is fully prerendered (every route is Static/SSG — see the
 * build output), so `output: "export"` emits a plain `out/` directory of
 * HTML/JS/CSS that any static host can serve. No Node server, no Vercel.
 *
 * GitHub project pages are served from a subpath
 * (`https://<user>.github.io/<repo>/`), so assets and routes must be
 * prefixed with that repo name. `basePath`/`assetPrefix` are driven by
 * `NEXT_PUBLIC_BASE_PATH` (set to `/civic-evals` in the deploy workflow)
 * and default to "" so `next dev` and a custom-domain build both serve
 * from root. `next/link` prepends `basePath` automatically; for raw
 * `<img>`/asset URLs use the `asset()` helper in `lib/basePath.ts`.
 */
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

const nextConfig: NextConfig = {
  output: "export",
  basePath: basePath || undefined,
  assetPrefix: basePath || undefined,
  // next/image's optimizer needs a server; static export can't run one.
  images: { unoptimized: true },
  // Emit `route/index.html` so deep links resolve without a rewrite engine.
  trailingSlash: true,
};

export default nextConfig;
