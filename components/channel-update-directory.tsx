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
  const initialItems = fullDirectory.items.slice(0, INITIAL_CHANNEL_UPDATE_LIMIT);
  const directory = {
    ...fullDirectory,
    items:
      channel === "technology"
        ? initialItems.slice(0, TECHNOLOGY_CHANNEL_UPDATE_LIMIT)
        : initialItems,
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
