#!/usr/bin/env python3
"""Production entrypoint combining research-object, event, evidence, and memory policy."""

from __future__ import annotations

try:
    from . import research_agent_article_events as article_events
    from . import research_agent_evidence_contract_v2 as evidence_contract_v2
    from . import research_agent_evidence_policy as evidence_policy
    from . import research_agent_research_objects as research_objects
    from . import research_agent_runtime as runtime
    from . import research_agent_thesis_memory as thesis_memory
except ImportError:  # Direct execution: python tools/research_agent_enhanced_runtime.py
    import research_agent_article_events as article_events  # type: ignore
    import research_agent_evidence_contract_v2 as evidence_contract_v2  # type: ignore
    import research_agent_evidence_policy as evidence_policy  # type: ignore
    import research_agent_research_objects as research_objects  # type: ignore
    import research_agent_runtime as runtime  # type: ignore
    import research_agent_thesis_memory as thesis_memory  # type: ignore


def main() -> int:
    runtime.install_runtime_policy()
    # Install data-source bridges before the strict evidence wrapper. The object
    # bridge reuses the canonical TS-exported technology/track identities and the
    # article bridge contributes high-value intelligence events. Evidence policy
    # remains the eligibility gate; contract v2 annotates verification/time
    # semantics, and Thesis Memory is outermost so it snapshots final public data.
    article_events.install_article_event_policy(runtime.agent)
    research_objects.install_research_object_policy(runtime.agent)
    research_objects.install_research_object_scope(evidence_policy)
    evidence_policy.install_evidence_policy(runtime.agent)
    evidence_contract_v2.install_evidence_contract(runtime.agent)
    thesis_memory.install_thesis_memory(runtime.agent)
    return runtime.agent.main()


if __name__ == "__main__":
    raise SystemExit(main())
