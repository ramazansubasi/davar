"""Tests asking Claude Code for the answer, with a stand-in program in its place. No Claude
Code, no network and no account are needed."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import ai  # noqa: E402
from common import DavarError  # noqa: E402

# a stand-in for Claude Code: answers as `claude -p --output-format json` does, as FAKE_CLAUDE says
STAND_IN = r'''
import json, os, sys
prompt = sys.stdin.buffer.read().decode("utf-8")
how = os.environ.get("FAKE_CLAUDE", "answer")
if how == "garbage":
    print("something went wrong", file=sys.stderr)
    sys.exit(3)
if how == "logged out":
    reply = {"type": "result", "is_error": True, "result": "Not logged in · Please run /login"}
else:
    reply = {"type": "result", "is_error": False,
             "result": json.dumps({"prompt": prompt, "arguments": sys.argv[1:], "folder": os.listdir(".")})}
sys.stdout.buffer.write(json.dumps(reply).encode("utf-8"))
'''


class AskingClaude(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        script = Path(self.folder.name) / "stand_in.py"
        script.write_text(STAND_IN, encoding="utf-8")
        if sys.platform == "win32":
            program = Path(self.folder.name) / "claude.cmd"
            program.write_text(f'@"{sys.executable}" "{script}" %*\n', encoding="utf-8")
        else:
            program = Path(self.folder.name) / "claude"
            program.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
            program.chmod(0o755)
        self.real = ai.claude_path
        ai.claude_path = lambda: program

    def tearDown(self):
        ai.claude_path = self.real
        os.environ.pop("FAKE_CLAUDE", None)
        self.folder.cleanup()

    def test_the_prompt_goes_in_and_the_answer_comes_back(self):
        prompt = "Başlık öner: Tuzla'nın ezilenlerinin sesi\nikinci satır"
        said = json.loads(ai.ask_claude(prompt))
        self.assertEqual(said["prompt"], prompt)
        self.assertEqual(said["arguments"][:3], ["-p", "--output-format", "json"])
        self.assertIn("--no-session-persistence", said["arguments"])
        self.assertEqual(said["arguments"][-2:], ["--tools", ""], "no tools: it can only read and answer")
        self.assertEqual(said["folder"], [], "it runs in an empty folder")

    def test_not_signed_in(self):
        os.environ["FAKE_CLAUDE"] = "logged out"
        with self.assertRaises(DavarError) as raised:
            ai.ask_claude("x")
        self.assertIn("/login", str(raised.exception))

    def test_an_answer_that_is_not_one(self):
        os.environ["FAKE_CLAUDE"] = "garbage"
        with self.assertRaises(DavarError) as raised:
            ai.ask_claude("x")
        self.assertIn("something went wrong", str(raised.exception))

    def test_not_installed(self):
        ai.claude_path = lambda: None
        with self.assertRaises(DavarError):
            ai.ask_claude("x")


if __name__ == "__main__":
    unittest.main()
