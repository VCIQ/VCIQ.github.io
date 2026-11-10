import { z } from "zod";

const originalUrl = /^https:\/\/mp\.weixin\.qq\.com\/s(?:\/[A-Za-z0-9_-]+|\?__biz=(?:[A-Za-z0-9._~+-]|%[0-9A-F]{2})+&mid=[0-9]+&idx=[0-9]+)$/u;

const publicText = (max: number) => z.string().min(1)
  .refine((value) => [...value].length <= max && value === value.trim() && !/[<>\u0000-\u001f\u007f]/u.test(value));

const media = z.array(z.strictObject({
  url: z.string().max(2048).refine((url) => url === url.trim() && originalUrl.test(url)),
  title: publicText(220),
  publisher: publicText(200),
  publishedAt: z.iso.date(),
})).max(100).refine((rows) => new Set(rows.map((row) => row.url)).size === rows.length);

export function parseInnovationWechatMedia(input: unknown) {
  const result = media.safeParse(input);
  if (!result.success) throw new Error("Invalid public innovation WeChat media snapshot");
  return result.data.sort((a, b) => b.publishedAt.localeCompare(a.publishedAt) || a.url.localeCompare(b.url));
}
