#!/usr/bin/env python3
"""Production entrypoint combining event, model runtime, evidence, and memory policy."""

from __future__ import annotations

try:
    from . import research_agent_article_events as article_events
    from . import research_agent_evidence_contract_v2 as evidence_contract_v2
    from . import research_agent_evidence_policy as evidence_policy
    from . import research_agent_runtime as runtime
    from . import research_agent_thesis_memory as thesis_memory
except ImportError:  # Direct execution: python tools/research_agent_enhanced_runtime.py
    import research_agent_article_events as article_events  # type: ignore
    import research_agent_evidence_contract_v2 as evidence_contract_v2  # type: ignore
    import research_agent_evidence_policy as evidence_policy  # type: ignore
    import research_agent_runtime as runtime  # type: ignore
    import research_agent_thesis_memory as thesis_memory  # type: ignore


def main() -> int:
    runtime.install_runtime_policy()
    # Install the event bridge before the strict evidence wrapper. The evidence
    # policy remains the eligibility gate; contract v2 only annotates the final
    # report with verification and temporal semantics after that decision.
    # Thesis memory is outermost because it snapshots the final public evidence
    # semantics and carries only bounded public-safe evidence metadata forward.
    article_events.install_article_event_policy(runtime.agent)
    evidence_policy.install_evidence_policy(runtime.agent)
    evidence_contract_v2.install_evidence_contract(runtime.agent)
    thesis_memory.install_thesis_memory(runtime.agent)
    return runtime.agent.main()


if __name__ == "__main__":
    raise SystemExit(main())
