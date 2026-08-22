import { ChannelUpdateDirectoryClient } from "@/components/channel-update-directory-client";
import {
  getChannelUpdateDirectory,
  type ChannelUpdateKey,
} from "@/lib/channel-updates";
import { aggregatePeopleUpdateDirectory } from "@/lib/people-event-updates";

const INITIAL_CHANNEL_UPDATE_LIMIT = 120;
const TECHNOLOGY_CHANNEL_UPDATE_LIMIT = 30;

export function ChannelUpdateDirectory({
  channel,
  layout = "default",
}: {
  channel: ChannelUpdateKey;
  layout?: "default" | "split";
}) {
  const rawDirectory = getChannelUpdateDirectory(channel);
  const fullDirectory =
    channel === "people" ? aggregatePeopleUpdateDirectory(rawDirectory) : rawDirectory;
  const initialItems =
    channel === "people"
      ? fullDirectory.items
      : fullDirectory.items.slice(0, INITIAL_CHANNEL_UPDATE_LIMIT);
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
