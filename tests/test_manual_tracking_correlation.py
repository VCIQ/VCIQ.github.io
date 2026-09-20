from __future__ import annotations
import hashlib
import json
import subprocess
import unittest
from pathlib import Path
from tools.manual_tracking_correlation import validate_correlation

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "12345678-1234-4234-8234-123456789abc"
BATCH = '[{"name":"公开示例","sourceUrl":"https://example.invalid/?x=1"}]'
def digest(batch=BATCH, policy="strict"):
    return hashlib.sha256(f"v1\n{policy}\n{batch}".encode()).hexdigest()

class CorrelationTests(unittest.TestCase):
    def test_legacy_is_compatible(self):
        self.assertFalse(validate_correlation("", "", "apply", "strict", BATCH))
        self.assertFalse(validate_correlation("", "", "validate", "skip", BATCH))
    def test_valid_public_bytes(self):
        for policy in ("strict", "skip"):
            self.assertTrue(validate_correlation(TOKEN, digest(policy=policy), "apply", policy, BATCH))
    def test_changed_bytes_policy_or_mode_rejected(self):
        for batch, policy, mode in ((BATCH+" ","strict","apply"),(BATCH,"skip","apply"),(BATCH,"strict","validate")):
            with self.assertRaises(ValueError): validate_correlation(TOKEN,digest(),mode,policy,batch)
    def test_partial_or_invalid_markers_rejected(self):
        for token, sha in ((TOKEN,""),("",digest()),("owner@example.invalid",digest()),(TOKEN,"private-value"),(TOKEN.replace("4234","8234"),digest())):
            with self.assertRaises(ValueError): validate_correlation(token,sha,"apply","strict",BATCH)
    def test_limits(self):
        batch="x"*45001
        with self.assertRaises(ValueError): validate_correlation(TOKEN,digest(batch),"apply","strict",batch)
    def test_error_does_not_echo_payload(self):
        with self.assertRaisesRegex(ValueError,"^dispatch_correlation_mismatch$"):
            validate_correlation(TOKEN,"0"*64,"apply","strict","PRIVATE_VALUE")
    def test_workflow_authorization_and_apply_gates_preserved(self):
        text=(ROOT/".github/workflows/manual-tracking-batch.yml").read_text()
        self.assertIn("workflow_dispatch:",text)
        self.assertIn("permissions: {}",text)
        self.assertNotIn("  schedule:",text)
        self.assertIn("name: Validate durable dispatch correlation v1",text)
        self.assertLess(text.index("Require both initiator"),text.index("name: Validate durable dispatch correlation v1"))
        self.assertIn("needs: authorize",text.split("  apply:",1)[1])
        self.assertIn("queue: max",text)
        self.assertIn("environment: tracking-admin",text)
        self.assertIn('test "$ACTUAL_REF" = "refs/heads/main"',text)
    def test_inputs_never_interpolated_into_shell(self):
        text=(ROOT/".github/workflows/manual-tracking-batch.yml").read_text()
        step=text.split("- name: Validate durable dispatch correlation v1",1)[1].split("\n  validate:",1)[0]
        self.assertEqual(step.split("run:",1)[1].strip(),"python tools/manual_tracking_correlation.py")
        self.assertIn("DISPATCH_TOKEN: ${{ inputs.dispatch_token }}",step)
    def test_javascript_and_python_frame_are_byte_identical(self):
        js="const c=require('node:crypto');let b=process.argv[1];process.stdout.write(c.createHash('sha256').update('v1\\nstrict\\n'+b,'utf8').digest('hex'));"
        got=subprocess.check_output(["node","-e",js,BATCH],text=True)
        self.assertEqual(got,digest())

if __name__ == "__main__": unittest.main()
