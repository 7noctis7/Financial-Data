import json
import subprocess
import sys
import unittest

from connectors import mcp_server
from mesh import iam


def _rpc(method, params=None, msg_id=1):
    msg = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params is not None:
        msg["params"] = params
    return msg


class TestMcpHandler(unittest.TestCase):
    def test_initialize_and_tools_list(self):
        init = mcp_server.handle(_rpc("initialize"), role="viewer")
        self.assertEqual(init["result"]["serverInfo"]["name"],
                         "financial-command-center")
        listing = mcp_server.handle(_rpc("tools/list"), role="viewer")
        names = [t["name"] for t in listing["result"]["tools"]]
        self.assertIn("catalog_list", names)
        self.assertIn("reconciliation_suggest", names)

    def test_public_tool_allowed_for_viewer(self):
        response = mcp_server.handle(
            _rpc("tools/call", {"name": "catalog_list", "arguments": {}}),
            role="viewer")
        self.assertFalse(response["result"]["isError"])
        catalog = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual(len(catalog), 10)

    def test_contextual_security_blocks_viewer(self):
        response = mcp_server.handle(
            _rpc("tools/call", {"name": "report_generate",
                                "arguments": {"template": "regulatory",
                                              "date": "2026-07-09"}}),
            role="viewer")
        self.assertTrue(response["result"]["isError"])
        self.assertIn("G9", response["result"]["content"][0]["text"])
        self.assertEqual(mcp_server._LOG.entries()[-1]["action"], "iam.denied")

    def test_reconciliation_tool_returns_lineage(self):
        response = mcp_server.handle(
            _rpc("tools/call", {"name": "reconciliation_suggest",
                                "arguments": {"date": "2026-07-09"}}),
            role="treasury-ops")
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertFalse(response["result"]["isError"])
        self.assertIn("lineage_proof", payload)

    def test_unknown_tool_and_method(self):
        bad_tool = mcp_server.handle(
            _rpc("tools/call", {"name": "rm_rf", "arguments": {}}), role="auditor")
        self.assertIn("error", bad_tool)
        bad_method = mcp_server.handle(_rpc("resources/list"), role="auditor")
        self.assertEqual(bad_method["error"]["code"], -32601)


class TestMcpStdio(unittest.TestCase):
    def test_end_to_end_over_stdio(self):
        messages = "\n".join(json.dumps(m) for m in [
            _rpc("initialize", msg_id=1),
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            _rpc("tools/list", msg_id=2),
            _rpc("tools/call", {"name": "catalog_list", "arguments": {}}, msg_id=3),
        ]) + "\n"
        proc = subprocess.run(
            [sys.executable, "-m", "connectors.mcp_server"],
            input=messages, capture_output=True, text=True, timeout=60,
            env={"FCC_ROLE": "viewer", "PATH": "/usr/bin:/bin"})
        responses = [json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual([r["id"] for r in responses], [1, 2, 3])
        self.assertFalse(responses[2]["result"]["isError"])


if __name__ == "__main__":
    unittest.main()
