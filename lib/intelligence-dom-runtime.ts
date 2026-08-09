export type IntelligenceDomScope = "favorite" | "hotness";

type IntelligenceDomListener = {
  id: number;
  priority: number;
  callback: (rows: readonly HTMLElement[]) => void;
};

type IdleHandle =
  | { kind: "idle"; id: number }
  | { kind: "timer"; id: number }
  | null;

type OptionalIdleApi = {
  requestIdleCallback?: (callback: () => void, options?: { timeout?: number }) => number;
  cancelIdleCallback?: (id: number) => void;
  setTimeout: (callback: () => void, delay?: number) => number;
  clearTimeout: (id: number) => void;
};

const FAVORITE_ROW_SELECTOR = [
  ".event-row",
  ".headlines-column a[class*='feedRow']",
  ".side-column a[class*='feedRow']",
  "[data-intelligence-item]",
  ".material-list > a",
  "a.source-card[href]",
  "a[class*='eventCard'][href]",
  ".market-news-item[href]",
  "[class*='eventList'] > a[href]",
  "[class*='newsList'] > a[href]",
  ".entity-list > a[target='_blank'][href]",
  ".analysis-grid > a[target='_blank'][href]",
].join(",");

const HOTNESS_ROW_SELECTOR = [
  FAVORITE_ROW_SELECTOR,
  ".favorite-intelligence-card",
  ".favorite-card",
].join(",");

const ALL_ROW_SELECTOR = HOTNESS_ROW_SELECTOR;
const TIMELINE_ROW_SELECTOR = ".timeline > div";

export const INTELLIGENCE_CONTROL_MOUNT_SELECTOR = [
  "[data-intelligence-favorite-mount]",
  "[data-intelligence-hotness-mount]",
].join(",");

const listeners = new Map<number, IntelligenceDomListener>();
const candidateRows = new Set<HTMLElement>();
const activeRows = new Set<HTMLElement>();
let nextListenerId = 1;
let mutationObserver: MutationObserver | null = null;
let intersectionObserver: IntersectionObserver | null = null;
let publishFrame = 0;
let refreshHandle: IdleHandle = null;

function idleApi(): OptionalIdleApi {
  return window as unknown as OptionalIdleApi;
}

function collectRows(): HTMLElement[] {
  const rows = new Set<HTMLElement>();
  document.querySelectorAll<HTMLElement>(ALL_ROW_SELECTOR).forEach((row) => rows.add(row));
  document.querySelectorAll<HTMLElement>(TIMELINE_ROW_SELECTOR).forEach((row) => {
    if (row.querySelector("a[href]")) rows.add(row);
  });
  return [...rows];
}

function isInsideControlMount(node: Node): boolean {
  if (node instanceof Element) {
    return (
      node.matches(INTELLIGENCE_CONTROL_MOUNT_SELECTOR) ||
      Boolean(node.closest(INTELLIGENCE_CONTROL_MOUNT_SELECTOR))
    );
  }
  return Boolean(node.parentElement?.closest(INTELLIGENCE_CONTROL_MOUNT_SELECTOR));
}

export function isControlOnlyMutation(record: MutationRecord): boolean {
  if (isInsideControlMount(record.target)) return true;
  const changedNodes = [...record.addedNodes, ...record.removedNodes];
  return changedNodes.length > 0 && changedNodes.every(isInsideControlMount);
}

function publishRows() {
  publishFrame = 0;
  if (!listeners.size) return;
  const rows = [...activeRows];
  const ordered = [...listeners.values()].sort(
    (left, right) => left.priority - right.priority || left.id - right.id,
  );
  for (const listener of ordered) listener.callback(rows);
}

function schedulePublish() {
  if (publishFrame || !listeners.size) return;
  publishFrame = window.requestAnimationFrame(publishRows);
}

function ensureIntersectionObserver() {
  if (intersectionObserver || typeof IntersectionObserver === "undefined") return;
  intersectionObserver = new IntersectionObserver(
    (entries) => {
      let entered = false;
      for (const entry of entries) {
        const row = entry.target as HTMLElement;
        if (entry.isIntersecting) {
          if (!activeRows.has(row)) {
            activeRows.add(row);
            entered = true;
          }
        } else {
          activeRows.delete(row);
        }
      }
      if (entered) schedulePublish();
    },
    {
      rootMargin: "1200px 0px",
      threshold: 0,
    },
  );
}

function refreshCandidates() {
  refreshHandle = null;
  if (!listeners.size) return;

  const nextRows = new Set(collectRows());
  const canObserveViewport = Boolean(intersectionObserver);

  for (const row of candidateRows) {
    if (nextRows.has(row) && row.isConnected) continue;
    intersectionObserver?.unobserve(row);
    candidateRows.delete(row);
    activeRows.delete(row);
  }

  for (const row of nextRows) {
    if (candidateRows.has(row)) continue;
    candidateRows.add(row);
    if (canObserveViewport) {
      intersectionObserver?.observe(row);
    } else {
      activeRows.add(row);
    }
  }

  if (!canObserveViewport) schedulePublish();
}

function cancelRefresh() {
  if (!refreshHandle) return;
  const api = idleApi();
  if (refreshHandle.kind === "idle" && typeof api.cancelIdleCallback === "function") {
    api.cancelIdleCallback(refreshHandle.id);
  } else {
    api.clearTimeout(refreshHandle.id);
  }
  refreshHandle = null;
}

function scheduleCandidateRefresh() {
  if (refreshHandle || !listeners.size) return;
  const api = idleApi();
  if (typeof api.requestIdleCallback === "function") {
    refreshHandle = {
      kind: "idle",
      id: api.requestIdleCallback(refreshCandidates, { timeout: 700 }),
    };
    return;
  }
  refreshHandle = {
    kind: "timer",
    id: api.setTimeout(refreshCandidates, 0),
  };
}

function ensureMutationObserver() {
  if (mutationObserver || typeof document === "undefined" || !document.body) return;
  mutationObserver = new MutationObserver((records) => {
    if (records.length > 0 && records.every(isControlOnlyMutation)) return;
    scheduleCandidateRefresh();
  });
  mutationObserver.observe(document.body, { childList: true, subtree: true });
}

export function subscribeIntelligenceDom(
  callback: (rows: readonly HTMLElement[]) => void,
  options: { priority?: number } = {},
): () => void {
  const id = nextListenerId;
  nextListenerId += 1;
  listeners.set(id, { id, priority: options.priority ?? 0, callback });
  ensureIntersectionObserver();
  ensureMutationObserver();
  scheduleCandidateRefresh();

  return () => {
    listeners.delete(id);
    if (listeners.size) return;

    mutationObserver?.disconnect();
    mutationObserver = null;
    intersectionObserver?.disconnect();
    intersectionObserver = null;
    cancelRefresh();
    if (publishFrame) window.cancelAnimationFrame(publishFrame);
    publishFrame = 0;
    candidateRows.clear();
    activeRows.clear();
  };
}

export function isIntelligenceDomRow(row: HTMLElement, scope: IntelligenceDomScope): boolean {
  if (row.matches(TIMELINE_ROW_SELECTOR)) return true;
  if (scope === "favorite") return row.matches(FAVORITE_ROW_SELECTOR);
  return row.matches(HOTNESS_ROW_SELECTOR);
}
