#!/usr/bin/env python3
"""Production runtime policy for the VCIQ Research Agent.

This adapter keeps the deterministic research implementation unchanged while
making the model call operationally safer:

* timeout/retry policy is controlled by environment variables;
* the model prompt is bounded without reducing the published change set;
* failures are classified and logged without exposing credentials;
* the existing deterministic fallback remains the final safety net.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError

try:
    from . import research_agent as agent
except ImportError:  # Direct execution: python tools/research_agent_runtime.py
    import research_agent as agent  # type: ignore


_ORIGINAL_CALL_SILICONFLOW = agent.call_siliconflow
_ORIGINAL_MODEL_PROMPT = agent._model_prompt
_ORIGINAL_FALLBACK_ANALYSIS = agent.fallback_analysis
_LAST_FAILURE: dict[str, Any] | None = None


class SiliconFlowRuntimeError(RuntimeError):
    """Base class for sanitized production model failures."""


class SiliconFlowTimeoutError(SiliconFlowRuntimeError):
    """The model did not answer within the configured request deadline."""


class SiliconFlowRateLimitError(SiliconFlowRuntimeError):
    """The provider rejected the request because of throttling or quota pressure."""


class SiliconFlowHTTPError(SiliconFlowRuntimeError):
    """The provider returned a non-retryable HTTP failure."""


class SiliconFlowTransportError(SiliconFlowRuntimeError):
    """The request failed before a valid HTTP response was received."""


class SiliconFlowResponseError(SiliconFlowRuntimeError):
    """The provider response could not satisfy the structured-output contract."""


def _env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


def _root_cause(exc: BaseException) -> BaseException:
    current = exc
    seen: set[int] = set()
    while id(current) not in seen:
        seen.add(id(current))
        cause = current.__cause__ or current.__context__
        if cause is None:
            break
        current = cause
    if isinstance(current, URLError) and isinstance(current.reason, BaseException):
        return current.reason
    return current


def _trace_id(exc: BaseException) -> str:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, HTTPError) and current.headers:
            for key in ("x-request-id", "x-trace-id", "trace-id", "cf-ray"):
                value = current.headers.get(key)
                if value:
                    return str(value)[:160]
        current = current.__cause__ or current.__context__
    return ""


def _find_http_error(exc: BaseException) -> HTTPError | None:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, HTTPError):
            return current
        current = current.__cause__ or current.__context__
    return None


def _find_url_error(exc: BaseException) -> URLError | None:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, URLError) and not isinstance(current, HTTPError):
            return current
        current = current.__cause__ or current.__context__
    return None


def _classify_failure(
    exc: BaseException, elapsed_seconds: float
) -> tuple[type[SiliconFlowRuntimeError], dict[str, Any]]:
    root = _root_cause(exc)
    diagnostic: dict[str, Any] = {
        "errorType": type(root).__name__,
        "elapsedSeconds": round(elapsed_seconds, 3),
    }
    trace_id = _trace_id(exc)
    if trace_id:
        diagnostic["traceId"] = trace_id

    if isinstance(root, TimeoutError):
        diagnostic["publicReason"] = "SiliconFlow 模型请求超时，已切换到规则引擎"
        return SiliconFlowTimeoutError, diagnostic

    http_error = _find_http_error(exc)
    if http_error is not None:
        diagnostic["httpStatus"] = http_error.code
        if http_error.code == 429:
            diagnostic["publicReason"] = "SiliconFlow 触发限流或配额压力，已切换到规则引擎"
            return SiliconFlowRateLimitError, diagnostic
        diagnostic["publicReason"] = f"SiliconFlow HTTP {http_error.code}，已切换到规则引擎"
        return SiliconFlowHTTPError, diagnostic

    if _find_url_error(exc) is not None:
        diagnostic["publicReason"] = "SiliconFlow 网络连接失败，已切换到规则引擎"
        return SiliconFlowTransportError, diagnostic

    if isinstance(root, (ValueError, json.JSONDecodeError)):
        diagnostic["publicReason"] = "SiliconFlow 返回结果未通过结构化校验，已切换到规则引擎"
        return SiliconFlowResponseError, diagnostic

    diagnostic["publicReason"] = "SiliconFlow 模型调用失败，已切换到规则引擎"
    return SiliconFlowRuntimeError, diagnostic


def call_siliconflow(
    *,
    api_key: str,
    base_url: str,
    model: str,
    reasoning_effort: str,
    prompt: str,
    timeout: float = 95.0,
    retries: int = 2,
) -> dict[str, Any]:
    """Apply production timeout/retry policy and emit credential-safe diagnostics."""

    del timeout, retries  # Production policy is environment-controlled by design.
    global _LAST_FAILURE

    configured_timeout = _env_float(
        "RESEARCH_AGENT_API_TIMEOUT", 180.0, minimum=15.0, maximum=600.0
    )
    configured_retries = _env_int(
        "RESEARCH_AGENT_API_RETRIES", 1, minimum=0, maximum=4
    )
    started = time.monotonic()
    print(
        json.dumps(
            {
                "event": "research_agent_model_request",
                "provider": "SiliconFlow",
                "model": model,
                "reasoningEffort": reasoning_effort,
                "timeoutSeconds": configured_timeout,
                "retries": configured_retries,
                "promptBytes": len(prompt.encode("utf-8")),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    try:
        result = _ORIGINAL_CALL_SILICONFLOW(
            api_key=api_key,
            base_url=base_url,
            model=model,
            reasoning_effort=reasoning_effort,
            prompt=prompt,
            timeout=configured_timeout,
            retries=configured_retries,
        )
    except Exception as exc:
        elapsed = time.monotonic() - started
        error_class, diagnostic = _classify_failure(exc, elapsed)
        diagnostic.update(
            {
                "event": "research_agent_model_failure",
                "provider": "SiliconFlow",
                "model": model,
            }
        )
        _LAST_FAILURE = diagnostic
        print(json.dumps(diagnostic, ensure_ascii=False), file=sys.stderr, flush=True)
        safe_message = str(
            diagnostic.get("publicReason") or "SiliconFlow model request failed"
        )
        raise error_class(safe_message) from exc

    elapsed = time.monotonic() - started
    _LAST_FAILURE = None
    print(
        json.dumps(
            {
                "event": "research_agent_model_success",
                "provider": "SiliconFlow",
                "model": model,
                "elapsedSeconds": round(elapsed, 3),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return result


def model_prompt(
    changes: list[dict[str, Any]], evidence: list[dict[str, Any]], as_of: str
) -> str:
    """Bound model context while preserving the full report's deterministic changes."""

    maximum = max(1, int(getattr(agent, "MAX_MODEL_CHANGES", 24)))
    limit = _env_int(
        "RESEARCH_AGENT_MODEL_CHANGE_LIMIT", 16, minimum=1, maximum=maximum
    )
    selected_changes = changes[:limit]
    evidence_ids = {
        str(evidence_id)
        for change in selected_changes
        if isinstance(change, Mapping)
        for evidence_id in change.get("evidenceIds", [])
        if isinstance(evidence_id, str)
    }
    selected_evidence = [
        row
        for row in evidence
        if isinstance(row, Mapping) and str(row.get("id") or "") in evidence_ids
    ]
    print(
        json.dumps(
            {
                "event": "research_agent_prompt_budget",
                "publishedChanges": len(changes),
                "modelChanges": len(selected_changes),
                "modelEvidence": len(selected_evidence),
                "modelChangeLimit": limit,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    prompt = _ORIGINAL_MODEL_PROMPT(selected_changes, selected_evidence, as_of)
    request_path = os.environ.get("RESEARCH_AGENT_NATIVE_REQUEST_PATH", "").strip()
    if not request_path:
        return prompt
    try:
        request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return prompt
    if not isinstance(request, Mapping) or not str(request.get("eventId") or "").strip():
        return prompt
    try:
        package = json.loads(prompt)
    except json.JSONDecodeError:
        return prompt
    if not isinstance(package, dict):
        return prompt
    package["nativeResearchRequest"] = {
        "eventId": str(request.get("eventId") or ""),
        "title": str(request.get("title") or ""),
        "url": str(request.get("url") or ""),
        "summary": str(request.get("summary") or ""),
        "sector": str(request.get("sector") or ""),
        "company": str(request.get("company") or ""),
        "publishedAt": str(request.get("publishedAt") or ""),
        "sourceName": str(request.get("sourceName") or ""),
        "sourceLevel": str(request.get("sourceLevel") or ""),
        "instruction": str(request.get("instruction") or ""),
    }
    package.setdefault("instructions", {})["nativeRequestPolicy"] = [
        "优先检查 nativeResearchRequest 是否能与本轮 evidence/changes 建立证据关系。",
        "若证据不足，必须明确写为待验证，不得用通用日报内容冒充事件专属结论。",
        "保持原 evidenceIds 约束；nativeResearchRequest 本身只是研究任务上下文，不是已验证证据。",
    ]
    return json.dumps(package, ensure_ascii=False, separators=(",", ":"))


def fallback_analysis(
    changes: list[dict[str, Any]], reason: str
) -> dict[str, Any]:
    """Replace the generic public fallback sentence with a safe concrete reason."""

    if reason == "模型调用或结果校验失败" and _LAST_FAILURE:
        reason = str(_LAST_FAILURE.get("publicReason") or reason)
    return _ORIGINAL_FALLBACK_ANALYSIS(changes, reason)


def install_runtime_policy() -> None:
    agent.call_siliconflow = call_siliconflow
    agent._model_prompt = model_prompt
    agent.fallback_analysis = fallback_analysis


def main() -> int:
    install_runtime_policy()
    return agent.main()


if __name__ == "__main__":
    raise SystemExit(main())
