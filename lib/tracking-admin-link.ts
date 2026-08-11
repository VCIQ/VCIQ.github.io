export interface TrackingCaptureLinkInput {
  url: string;
  title?: string;
  summary?: string;
  keywords?: string[];
  source?: string;
  channel?: string;
}

const DEFAULT_TRACKING_ADMIN = "https://vciq-tracking-console.pages.dev";

export function buildTrackingCaptureLink(input: TrackingCaptureLinkInput): string {
  const base = (process.env.NEXT_PUBLIC_TRACKING_ADMIN_URL || DEFAULT_TRACKING_ADMIN).replace(/\/+$/, "");
  const params = new URLSearchParams();
  params.set("url", input.url);
  if (input.title) params.set("title", input.title.slice(0, 500));
  if (input.summary) params.set("summary", input.summary.slice(0, 1600));
  if (input.keywords?.length) params.set("keywords", input.keywords.slice(0, 30).join("|"));
  if (input.source) params.set("source", input.source.slice(0, 160));
  if (input.channel) params.set("channel", input.channel.slice(0, 80));
  return `${base}/capture?${params.toString()}`;
}
