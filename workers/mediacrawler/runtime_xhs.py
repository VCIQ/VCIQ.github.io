"""XHS pinned upstream wiring. Called only inside the isolated subprocess."""

async def setup(context, page):
    from media_platform.xhs.core import XiaoHongShuCrawler
    crawler = XiaoHongShuCrawler()
    crawler.browser_context, crawler.context_page = context, page
    await page.goto(crawler.index_url, wait_until="domcontentloaded", timeout=30000)
    client = await crawler.create_xhs_client(None)
    return client, crawler.cookie_urls


async def collect(client, observer_module, observer):
    from store import xhs as store
    capture = observer_module.CaptureStore(observer)
    store.XhsStoreFactory.create_store = staticmethod(lambda: capture)
    await observer_module.xhs_search(client, store, observer)
