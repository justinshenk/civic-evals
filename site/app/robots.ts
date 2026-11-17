import type { MetadataRoute } from "next";

// Required so the route prerenders to a static robots.txt under
// `output: "export"` (no server runtime to generate it on request).
export const dynamic = "force-static";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: "/preview/",
      },
    ],
  };
}
