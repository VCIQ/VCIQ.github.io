import { ChannelUpdateDirectoryClient } from "@/components/channel-update-directory-client";
import { curateCompanyUpdateDirectory } from "@/lib/company-update-curation";
import {
  getChannelUpdateDirectory,
  type ChannelUpdateKey,
} from "@/lib/channel-updates";
import { aggregatePeopleUpdateDirectory } from "@/lib/people-event-updates";

const INITIAL_CHANNEL_UPDATE_LIMIT = 120;
const TECHNOLOGY_CHANNEL_UPDATE_LIMIT = 30;
const PEOPLE_CHANNEL_UPDATE_LIMIT = 40;
const COMPANY_CHANNEL_UPDATE_LIMIT = 24;

export function ChannelUpdateDirectory({
  channel,
  layout = "default",
}: {
  channel: ChannelUpdateKey;
  layout?: "default" | "split";
}) {
  const rawDirectory = getChannelUpdateDirectory(channel);
  const preparedDirectory =
    channel === "companies"
      ? curateCompanyUpdateDirectory(rawDirectory)
      : rawDirectory;
  const fullDirectory =
    channel === "people"
      ? aggregatePeopleUpdateDirectory(preparedDirectory)
      : preparedDirectory;
  const initialItems = fullDirectory.items.slice(0, INITIAL_CHANNEL_UPDATE_LIMIT);
  const directory = {
    ...fullDirectory,
    items:
      channel === "technology"
        ? initialItems.slice(0, TECHNOLOGY_CHANNEL_UPDATE_LIMIT)
        : channel === "people"
          ? initialItems.slice(0, PEOPLE_CHANNEL_UPDATE_LIMIT)
          : channel === "companies"
            ? initialItems.slice(0, COMPANY_CHANNEL_UPDATE_LIMIT)
            : initialItems,
  };
  const totalItemCount =
    channel === "companies" ? directory.items.length : fullDirectory.items.length;

  return (
    <ChannelUpdateDirectoryClient
      channel={channel}
      directory={directory}
      totalItemCount={totalItemCount}
      layout={layout}
    />
  );
}
