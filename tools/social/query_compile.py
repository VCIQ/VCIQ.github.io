"""Compile one literal term; never truncate it or invent platform Boolean syntax."""
from __future__ import annotations

from urllib.parse import urlencode

from .contracts import ContractError, assert_safe, normalize_query

WECHAT_PROVIDERS = ("sogou-weixin", "bing-rss")


def compile_query(platform: str, provider: str, term: str, *, account: str | None = None) -> str:
    term = normalize_query(term)
    assert_safe(term)
    if not term:
        raise ContractError("empty_term")
    if any(ord(char) < 32 for char in term):
        raise ContractError("query_control_character")
    if account is not None:
        account = normalize_query(account)
        assert_safe(account)
        if not account:
            raise ContractError("empty_account")
    if platform == "wechat":
        if provider == "sogou-weixin":
            text = f"{account} {term}" if account else term
            if len(text) > 38:
                raise ContractError("sogou_query_too_long")
        elif provider == "bing-rss":
            if '"' in term or (account and '"' in account):
                raise ContractError("query_requires_manual_quoting")
            text = 'site:mp.weixin.qq.com/s ' + (f'"{account}" ' if account else "") + f'"{term}"'
        else:
            raise ContractError("provider_not_implemented")
    else:
        if provider != "mediacrawler" or account is not None:
            raise ContractError("provider_scope_mismatch")
        if "," in term:
            raise ContractError("query_requires_manual_comma")
        text = term
    if len(text) > 512:
        raise ContractError("query_too_long")
    return text


def search_url(job: dict, page: int) -> str:
    if job["platform"] != "wechat" or not 1 <= page <= job["limits"]["maxSearchPages"]:
        raise ContractError("search_page")
    text = job["query"]["text"]
    if job["provider"] == "sogou-weixin":
        if len(text) > 38:
            raise ContractError("sogou_query_too_long")
        # Explicit query is essential: the production default otherwise chooses a prefix term.
        from tools.wechat_sogou_index import build_search_url
        return build_search_url({}, page=page, query=text)
    if job["provider"] == "bing-rss":
        if page != 1:
            raise ContractError("provider_has_no_pagination")
        return "https://www.bing.com/search?" + urlencode({"format": "rss", "q": text})
    raise ContractError("provider_not_implemented")
