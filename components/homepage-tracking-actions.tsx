"use client";

import { BookmarkPlus } from "lucide-react";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { buildTrackingCaptureLink } from "@/lib/tracking-admin-link";
import styles from "./homepage-tracking-actions.module.css";

type EventTarget = {
  row: HTMLElement;
  mount: HTMLElement;
};

type CompanyTarget = {
  anchor: HTMLAnchorElement;
};

function openCapture(input: Parameters<typeof buildTrackingCaptureLink>[0]) {
  window.open(
    buildTrackingCaptureLink(input),
    "_blank",
    "noopener,noreferrer",
  );
}

function eventCaptureInput(row: HTMLElement) {
  const sourceLink = row.querySelector<HTMLAnchorElement>("a.source-link");
  const title = row.querySelector<HTMLElement>("h3")?.textContent?.trim() ?? "";
  const summary = row.querySelector<HTMLElement>(".event-main > p")?.textContent?.trim() ?? "";
  const keywords = [...row.querySelectorAll<HTMLElement>(".event-tags span")]
    .map((node) => node.textContent?.trim() ?? "")
    .filter(Boolean);
  return sourceLink?.href && title
    ? {
        url: sourceLink.href,
        title,
        summary,
        keywords,
        source: sourceLink.textContent?.replace(/\s+/g, " ").trim() ?? "",
        channel: "homepage-key-event",
      }
    : null;
}

function companyCaptureInput(anchor: HTMLAnchorElement) {
  const title = anchor.querySelector<HTMLElement>("h3")?.textContent?.trim() ?? "";
  const summary = anchor.querySelector<HTMLElement>("p")?.textContent?.trim() ?? "";
  return title
    ? {
        url: anchor.href,
        title: `公司：${title}`,
        summary,
        keywords: [title],
        source: "VCIQ",
        channel: "homepage-focus-company",
      }
    : null;
}

export function HomepageTrackingActions() {
  const [eventTargets, setEventTargets] = useState<EventTarget[]>([]);
  const [companyTargets, setCompanyTargets] = useState<CompanyTarget[]>([]);

  useEffect(() => {
    let scheduled = 0;

    const scan = () => {
      scheduled = 0;
      const nextEvents = [...document.querySelectorAll<HTMLElement>(".event-row")]
        .map((row) => ({ row, mount: row.querySelector<HTMLElement>(".event-main") }))
        .filter((target): target is EventTarget => Boolean(target.mount));

      const researchRoot = document.querySelector<HTMLElement>(
        'section[aria-label="首页研究概览"]',
      );
      const nextCompanies = researchRoot
        ? [...researchRoot.querySelectorAll<HTMLAnchorElement>('a[href*="/companies/"]')]
            .filter((anchor) => Boolean(anchor.querySelector("h3")))
            .map((anchor) => ({ anchor }))
        : [];

      setEventTargets(nextEvents);
      setCompanyTargets(nextCompanies);
    };

    const scheduleScan = () => {
      if (scheduled) return;
      scheduled = window.requestAnimationFrame(scan);
    };

    scan();
    const observer = new MutationObserver(scheduleScan);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => {
      observer.disconnect();
      if (scheduled) window.cancelAnimationFrame(scheduled);
    };
  }, []);

  return (
    <>
      {eventTargets.map(({ row, mount }) =>
        createPortal(
          <button
            type="button"
            className={styles.eventAction}
            onClick={() => {
              const input = eventCaptureInput(row);
              if (input) openCapture(input);
            }}
            title="从这条关键事件提取并加入追踪"
          >
            <BookmarkPlus size={12} aria-hidden="true" />
            加入追踪
          </button>,
          mount,
          `event:${row.getAttribute("data-id") ?? row.textContent?.slice(0, 80) ?? "row"}`,
        ),
      )}

      {companyTargets.map(({ anchor }) =>
        createPortal(
          <span
            className={styles.companyAction}
            role="button"
            tabIndex={0}
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              const input = companyCaptureInput(anchor);
              if (input) openCapture(input);
            }}
            onKeyDown={(event) => {
              if (event.key !== "Enter" && event.key !== " ") return;
              event.preventDefault();
              event.stopPropagation();
              const input = companyCaptureInput(anchor);
              if (input) openCapture(input);
            }}
            title="把这家公司加入追踪"
          >
            <BookmarkPlus size={11} aria-hidden="true" />
            加入追踪
          </span>,
          anchor,
          `company:${anchor.pathname}`,
        ),
      )}
    </>
  );
}
