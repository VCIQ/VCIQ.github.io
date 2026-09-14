import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "丽泽路1号｜VCIQ",
    short_name: "VCIQ",
    description: "一级市场科技研究与情报阅读。",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#f3f2ec",
    theme_color: "#f3f2ec",
    orientation: "portrait-primary",
    lang: "zh-CN",
    icons: [
      {
        src: "/favicon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
    ],
  };
}
