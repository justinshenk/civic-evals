/**
 * Base path the site is served under, mirrored from `next.config.ts`.
 *
 * `next/link` and the Next metadata/icon handling prepend `basePath`
 * automatically, but raw `<img>` tags and other hand-written asset URLs
 * do not — wrap those in `asset()` so they resolve correctly when the
 * site is hosted under a subpath (GitHub project pages) and at root
 * (local dev, custom domain) alike.
 */
export const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

export function asset(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${basePath}${normalized}`;
}
