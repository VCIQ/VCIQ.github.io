import { ImageResponse } from "next/og";
import {
  SITE_SHARE_IMAGE_SIZE,
  SiteShareImage,
} from "@/components/site-share-image";

export const dynamic = "force-static";

export function GET() {
  return new ImageResponse(<SiteShareImage />, SITE_SHARE_IMAGE_SIZE);
}
