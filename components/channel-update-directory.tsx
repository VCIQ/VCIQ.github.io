import { ChannelUpdateDirectoryClient } from "@/components/channel-update-directory-client";
import {
  getChannelUpdateDirectory,
  type ChannelUpdateKey,
} from "@/lib/channel-updates";

const INITIAL_CHANNEL_UPDATE_LIMIT = 120;
const TECHNOLOGY_CHANNEL_UPDATE_LIMIT = 100;

export function ChannelUpdateDirectory({
  channel,
  layout = "default",
}: {
  channel: ChannelUpdateKey;
  layout?: "default" | "split";
}) {
  const fullDirectory = getChannelUpdateDirectory(channel);
  const initialLimit =
    channel === "technology" ? TECHNOLOGY_CHANNEL_UPDATE_LIMIT : INITIAL_CHANNEL_UPDATE_LIMIT;
  const directory = {
    ...fullDirectory,
    items: fullDirectory.items.slice(0, initialLimit),
  };

  return (
    <ChannelUpdateDirectoryClient
      channel={channel}
      directory={directory}
      totalItemCount={fullDirectory.items.length}
      layout={layout}
    />
  );
}
