"""Narrow, explainable background gate, not semantic fact verification.

Only obvious explainers without concrete report cues are held out of the event
queue. Ambiguous/mixed reporting remains reviewable. Content is never deleted.
"""
from __future__ import annotations

import re
import unicodedata

VERSION = "social-background-gate-v1"
EXPLAINER = re.compile(
    r"科普|入门|教程|看懂|读懂|什么是|何为|一文了解|概念解析|基础知识|原理讲解|"
    r"\b(?:explained|explainer|tutorial|beginners?|introduction to|what is|what are)\b", re.I)
DEFINITION = re.compile(r"是指|指的是|简单来说|通俗地说|区别在于|基本概念|\b(?:refers to|is defined as)\b", re.I)
HYPOTHETICAL = re.compile(r"如果|假如|假设|例如|比如|举例|假想|\b(?:if|suppose|imagine|for example|hypothetically)\b", re.I)
EVENTS = tuple(re.compile(pattern, re.I) for pattern in (
    r"(?:完成|获得|获|宣布)[^。！？.!?\n]{0,36}(?:融资|领投)",
    r"(?:提交|递交|披露|通过)[^。！？.!?\n]{0,24}(?:招股书|上市申请|上市审核|上市辅导)",
    r"(?:正式|首次|宣布|已经)[^。！？.!?\n]{0,8}(?:发布|推出|量产|上线|开源)[^。！？.!?\n]{1,60}",
    r"(?:公司|企业|团队|实验室|大学|研究院)[^。！？.!?\n]{0,16}(?:发布|推出|开源|投产|签约|成立|申请专利)[^。！？.!?\n]{1,60}",
    r"\b(?:raised|secured|closed)\b[^.!?\n]{0,50}\b(?:funding|financing|round|million|billion)\b",
    r"\b(?:announced|launched|released|unveiled|filed)\b[^.!?\n]{0,50}\b(?:product|model|robot|patent|ipo|listing)\b",
))


def classify_material(title, excerpt):
    title = unicodedata.normalize("NFKC", title)
    excerpt = unicodedata.normalize("NFKC", excerpt)
    explainer = bool(EXPLAINER.search(title)) or len(DEFINITION.findall(excerpt)) >= 2
    # Do not concatenate across title/sentence boundaries to invent an event.
    sentences = re.split(r"[。！？.!?\n]+", title + "\n" + excerpt)
    event = any(not HYPOTHETICAL.search(sentence) and any(pattern.search(sentence) for pattern in EVENTS)
                for sentence in sentences)
    background = explainer and not event
    return {"policyVersion": VERSION, "disposition": "background" if background else "reviewable",
            "reason": "EXPLAINER_WITHOUT_EVENT_CUE" if background else "MIXED_REPORT_REQUIRES_REVIEW" if explainer else "NOT_OBVIOUS_EXPLAINER",
            "explainerCue": explainer, "concreteReportCue": event,
            "factVerified": False}
