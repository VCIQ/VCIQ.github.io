from __future__ import annotations

import copy
import unittest

from tools.stabilize_venture_guarded_publication import (
    stabilize_guarded_publication_snapshot,
)


class GuardedVenturePublicationTests(unittest.TestCase):
    def test_guard_can_absorb_repeat_upstream_noise(self) -> None:
        def publication(snapshot, _articles, _catalog, *, max_passes=8):
            result = copy.deepcopy(snapshot)
            result["crossFieldNoise"] = "rediscovered"
            return result, {"maxPasses": max_passes}

        def guard(snapshot, _catalog):
            result = copy.deepcopy(snapshot)
            result.pop("crossFieldNoise", None)
            return result, {"removed": 1}

        stabilized, diagnostics = stabilize_guarded_publication_snapshot(
            {"value": 1},
            {},
            "",
            publication_stabilizer=publication,
            cross_field_guard=guard,
        )

        self.assertEqual(stabilized, {"value": 1})
        self.assertTrue(diagnostics["converged"])
        self.assertEqual(diagnostics["passes"], 1)
        self.assertEqual(diagnostics["changedPasses"], 0)

    def test_cross_pass_publication_updates_converge(self) -> None:
        def publication(snapshot, _articles, _catalog, *, max_passes=8):
            result = copy.deepcopy(snapshot)
            result["value"] = min(int(result["value"]) + 1, 2)
            return result, {"maxPasses": max_passes}

        def identity_guard(snapshot, _catalog):
            return copy.deepcopy(snapshot), {"removed": 0}

        stabilized, diagnostics = stabilize_guarded_publication_snapshot(
            {"value": 0},
            {},
            "",
            publication_stabilizer=publication,
            cross_field_guard=identity_guard,
        )

        self.assertEqual(stabilized, {"value": 2})
        self.assertTrue(diagnostics["converged"])
        self.assertEqual(diagnostics["passes"], 2)

    def test_guard_cycle_is_rejected(self) -> None:
        def identity_publication(snapshot, _articles, _catalog, *, max_passes=8):
            return copy.deepcopy(snapshot), {"maxPasses": max_passes}

        def toggle_guard(snapshot, _catalog):
            result = copy.deepcopy(snapshot)
            result["flag"] = not bool(result["flag"])
            return result, {"toggled": 1}

        with self.assertRaisesRegex(RuntimeError, "entered a cycle"):
            stabilize_guarded_publication_snapshot(
                {"flag": False},
                {},
                "",
                publication_stabilizer=identity_publication,
                cross_field_guard=toggle_guard,
            )


if __name__ == "__main__":
    unittest.main()
