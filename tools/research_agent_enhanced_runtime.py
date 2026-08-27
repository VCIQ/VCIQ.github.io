#!/usr/bin/env python3
"""Production entrypoint combining event, model runtime, and strict evidence policy."""

from __future__ import annotations

try:
    from . import research_agent_article_events as article_events
    from . import research_agent_evidence_policy as evidence_policy
    from . import research_agent_runtime as runtime
except ImportError:  # Direct execution: python tools/research_agent_enhanced_runtime.py
    import research_agent_article_events as article_events  # type: ignore
    import research_agent_evidence_policy as evidence_policy  # type: ignore
    import research_agent_runtime as runtime  # type: ignore


def main() -> int:
    runtime.install_runtime_policy()
    # Install the event bridge before the evidence wrapper. The strict evidence
    # policy therefore remains the outer/final eligibility gate.
    article_events.install_article_event_policy(runtime.agent)
    evidence_policy.install_evidence_policy(runtime.agent)
    return runtime.agent.main()


if __name__ == "__main__":
    raise SystemExit(main())
