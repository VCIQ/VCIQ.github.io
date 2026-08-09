import {
  GITHUB_API_ROOT,
  base64ToText,
  githubJson,
} from "@/lib/github-commit";
import { assertNoNewCompoundTrackingEntities } from "@/lib/tracking-entity-integrity";
import {
  TRACKING_BRANCH,
  TRACKING_CONFIG_PATH,
  TRACKING_OWNER,
  TRACKING_REPOSITORY,
  normalizeTrackingConfig,
  type UserTrackingConfig,
} from "@/lib/user-tracking";
import {
  TRACKING_CAPTURE_INBOX_PATH,
  normalizeTrackingCaptureInbox,
  type TrackingCaptureInbox,
} from "@/lib/tracking-capture";

export type TrackingCaptureRepositoryState = {
  headSha: string;
  treeSha: string;
  username: string;
  config: UserTrackingConfig;
  inbox: TrackingCaptureInbox;
};

export class TrackingCaptureConflictError extends Error {
  constructor(message = "远端配置已变化，请基于最新版本重新提交。") {
    super(message);
    this.name = "TrackingCaptureConflictError";
  }
}

async function fetchTextAtRef(
  token: string,
  path: string,
  ref: string,
): Promise<string> {
  const file = await githubJson<{ content?: string }>(
    `${GITHUB_API_ROOT}/repos/${TRACKING_REPOSITORY}/contents/${path}?ref=${encodeURIComponent(ref)}`,
    token,
  );
  if (!file.content) throw new Error(`GitHub 未返回 ${path} 的文件内容。`);
  return base64ToText(file.content);
}

export async function fetchTrackingCaptureRepositoryState(
  token: string,
): Promise<TrackingCaptureRepositoryState> {
  const user = await githubJson<{ login: string }>(`${GITHUB_API_ROOT}/user`, token);
  if (user.login.toLowerCase() !== TRACKING_OWNER.toLowerCase()) {
    throw new Error(`当前账号 ${user.login} 不是仓库所有者 ${TRACKING_OWNER}。`);
  }

  const ref = await githubJson<{ object?: { sha?: string } }>(
    `${GITHUB_API_ROOT}/repos/${TRACKING_REPOSITORY}/git/ref/heads/${TRACKING_BRANCH}`,
    token,
  );
  const headSha = ref.object?.sha ?? "";
  if (!headSha) throw new Error("GitHub 未返回 main 分支头部 SHA。");
  const commit = await githubJson<{ tree?: { sha?: string } }>(
    `${GITHUB_API_ROOT}/repos/${TRACKING_REPOSITORY}/git/commits/${headSha}`,
    token,
  );
  const treeSha = commit.tree?.sha ?? "";
  if (!treeSha) throw new Error("GitHub 未返回 main 分支树 SHA。");

  const [configText, inboxText] = await Promise.all([
    fetchTextAtRef(token, TRACKING_CONFIG_PATH, headSha),
    fetchTextAtRef(token, TRACKING_CAPTURE_INBOX_PATH, headSha),
  ]);

  return {
    headSha,
    treeSha,
    username: user.login,
    config: normalizeTrackingConfig(JSON.parse(configText)),
    inbox: normalizeTrackingCaptureInbox(JSON.parse(inboxText)),
  };
}

async function createBlob(token: string, content: string): Promise<string> {
  const blob = await githubJson<{ sha?: string }>(
    `${GITHUB_API_ROOT}/repos/${TRACKING_REPOSITORY}/git/blobs`,
    token,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, encoding: "utf-8" }),
    },
  );
  if (!blob.sha) throw new Error("GitHub 未返回新文件 blob SHA。");
  return blob.sha;
}

export async function commitTrackingCaptureRepositoryState(
  token: string,
  state: TrackingCaptureRepositoryState,
  next: { config: UserTrackingConfig; inbox: TrackingCaptureInbox },
): Promise<string> {
  assertNoNewCompoundTrackingEntities(state.config, next.config);

  const latestRef = await githubJson<{ object?: { sha?: string } }>(
    `${GITHUB_API_ROOT}/repos/${TRACKING_REPOSITORY}/git/ref/heads/${TRACKING_BRANCH}`,
    token,
  );
  if (latestRef.object?.sha !== state.headSha) {
    throw new TrackingCaptureConflictError();
  }

  const [configBlob, inboxBlob] = await Promise.all([
    createBlob(token, `${JSON.stringify(next.config, null, 2)}\n`),
    createBlob(token, `${JSON.stringify(next.inbox, null, 2)}\n`),
  ]);
  const tree = await githubJson<{ sha?: string }>(
    `${GITHUB_API_ROOT}/repos/${TRACKING_REPOSITORY}/git/trees`,
    token,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        base_tree: state.treeSha,
        tree: [
          {
            path: TRACKING_CONFIG_PATH,
            mode: "100644",
            type: "blob",
            sha: configBlob,
          },
          {
            path: TRACKING_CAPTURE_INBOX_PATH,
            mode: "100644",
            type: "blob",
            sha: inboxBlob,
          },
        ],
      }),
    },
  );
  if (!tree.sha) throw new Error("GitHub 未返回新树 SHA。");

  const commit = await githubJson<{ sha?: string }>(
    `${GITHUB_API_ROOT}/repos/${TRACKING_REPOSITORY}/git/commits`,
    token,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: "config: capture tracking entities from article",
        tree: tree.sha,
        parents: [state.headSha],
      }),
    },
  );
  if (!commit.sha) throw new Error("GitHub 未返回采集提交 SHA。");

  try {
    await githubJson(
      `${GITHUB_API_ROOT}/repos/${TRACKING_REPOSITORY}/git/refs/heads/${TRACKING_BRANCH}`,
      token,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sha: commit.sha, force: false }),
      },
    );
  } catch (error) {
    const status = (error as Error & { status?: number }).status;
    if (status === 409 || status === 422) throw new TrackingCaptureConflictError();
    throw error;
  }
  return commit.sha;
}
