"""Fixed capability allowlist; no arbitrary plugin/module paths from a job."""
from pathlib import Path

CANDIDATES = {"xhs": "xhs", "wb": "weibo", "bili": "bilibili", "zhihu": "zhihu"}
HOSTS = {
    "xhs": ("xiaohongshu.com", "xhscdn.com", "xhscdn.net"),
    "wb": ("weibo.com", "weibo.cn", "sina.com.cn", "sinaimg.cn", "sinajs.cn"),
    "bili": ("bilibili.com", "biliapi.net", "bilivideo.com", "hdslb.com"),
    "zhihu": ("zhihu.com", "zhimg.com"),
}


def available(root):
    root = Path(root)
    return {platform: name for platform, name in CANDIDATES.items()
            if (root / "tools/social/adapters" / (name + ".py")).is_file()
            and (root / "workers/mediacrawler" / ("runtime_" + name + ".py")).is_file()}
