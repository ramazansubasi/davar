"""davar ai - asks Claude Code, when it is installed on this computer, instead of a chat in the browser.

Content Analysis writes a prompt for an AI. It can be pasted into any AI chat; with Claude
Code (Anthropic's command-line program) installed and signed in, Davar hands it the prompt
itself and reads back the answer, with the user's own Claude subscription and no key.

Claude Code is run with none of its tools, in an empty folder of its own and without saving
the conversation: it reads the prompt and writes an answer, nothing else. What it is sent is
what would be pasted into the chat: the transcript and the notes of the Content Analysis page.
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from common import NO_WINDOW, DavarError
from i18n import _

WAIT = 15 * 60  # seconds; the answer for a long programme takes a few minutes


def claude_path():
    """Where Claude Code is installed, or None: on the PATH, or where its installer puts it."""
    found = shutil.which("claude")
    if found:
        return Path(found)
    home = Path.home()
    for place in (home / ".local" / "bin" / "claude.exe", home / ".local" / "bin" / "claude",
                  Path(os.environ.get("APPDATA", home)) / "npm" / "claude.cmd"):
        if place.is_file():
            return place
    return None


def ask_claude(prompt, wait=WAIT):
    """Claude Code's answer to `prompt` (text)."""
    program = claude_path()
    if program is None:
        raise DavarError(_("Claude Code is not installed on this computer; copy the prompt into an AI chat instead."))
    with tempfile.TemporaryDirectory(prefix="davar_ai_") as folder:
        try:
            done = subprocess.run([str(program), "-p", "--output-format", "json", "--no-session-persistence",
                                   "--tools", ""], input=prompt.encode("utf-8"), capture_output=True,
                                  cwd=folder, timeout=wait, creationflags=NO_WINDOW)
        except subprocess.TimeoutExpired:
            raise DavarError(_("Claude Code gave no answer in {minutes} minutes.").format(minutes=wait // 60))
        except OSError as e:
            raise DavarError(_("Claude Code could not be started: {message}").format(message=e))
    # read and written as bytes: in text mode Windows would turn every line end into two characters
    output, errors = (done.stdout or b"").decode("utf-8", "replace"), (done.stderr or b"").decode("utf-8", "replace")
    try:
        reply = json.loads(output)
    except ValueError:
        said = (errors or output).strip().splitlines()
        raise DavarError(_("Claude Code did not answer: {message}").format(message=said[-1] if said else done.returncode))
    text = str(reply.get("result") or "").strip()
    if reply.get("is_error") or not text:
        if "login" in text.lower() or "logged in" in text.lower():
            raise DavarError(_("Claude Code is not signed in. Open a terminal, type claude, sign in with /login, "
                               "and try again."))
        raise DavarError(_("Claude Code did not answer: {message}").format(message=text or _("an empty answer")))
    return text
