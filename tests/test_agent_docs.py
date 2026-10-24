"""The agent-facing docs: commands that work from every operator shell, and
prompts and versions that stay in sync.

Agents copy commands from these files verbatim, from PowerShell, cmd, Git
Bash, zsh or bash. A remote command that only works in one of them is a bug,
so this lints every `ssh <host> ...` command in the docs against the rule in
skills/caml-benchmark/references/camlctl.md: plain words, or one pair of
double quotes with no $, backtick, %, ! or " inside.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "caml-benchmark"
REFS = SKILL / "references"
PROMPT_DOC = ROOT / "docs" / "getting-started" / "agent-prompt.md"
README = ROOT / "README.md"
OSES = {"windows": "operator-windows.md", "macos": "operator-macos.md", "linux": "operator-linux.md"}

AGENT_DOCS = [README, PROMPT_DOC, SKILL / "SKILL.md", *sorted(REFS.glob("*.md"))]


def _version() -> str:
    text = (ROOT / "src" / "caml" / "__version__.py").read_text()
    return re.search(r'^__version__ = "(.*)"$', text, re.M).group(1)


def _code_snippets(text: str) -> list[str]:
    """Lines of fenced code blocks, plus inline `code` spans elsewhere."""
    out, in_fence = [], False
    for line in text.splitlines():
        if re.match(r"^\s*(```|~~~)", line):
            in_fence = not in_fence
            continue
        if in_fence:
            out.append(line.strip())
            # Prompts sit in ```text blocks and quote commands inline.
            out.extend(re.findall(r"`([^`]+)`", line))
        else:
            out.extend(re.findall(r"`([^`]+)`", line))
    return out


# ssh [options] TARGET [remote command]; -o, -i, -p, -F, ... take a value, -t, -T, -v, ... don't.
SSH_CMD = re.compile(r"(?:^|[|;]\s*|&&\s*)ssh((?:\s+-[oipFlJLRDEbcemOQSWw]\s+\S+|\s+-[A-Za-z0-9]+)*)\s+([A-Za-z0-9_<>.\-]+(?:@[A-Za-z0-9_<>.\-]+)?)(?:\s+(.*))?$")
BARE_OK = re.compile(r"^[A-Za-z0-9_./:=,@+ -]*$")
QUOTED_OK = re.compile(r'^"[^"$`%!]*"$')


def _remote_commands():
    for doc in AGENT_DOCS:
        for snippet in _code_snippets(doc.read_text()):
            m = SSH_CMD.search(snippet)
            if m and m.group(3):
                yield doc.relative_to(ROOT).as_posix(), snippet, m.group(3).strip()


REMOTE = list(_remote_commands())


def test_docs_contain_remote_commands():
    assert len(REMOTE) > 30  # the linter actually finds them


@pytest.mark.parametrize("doc,snippet,remote", REMOTE, ids=[f"{d}: {r[:50]}" for d, _, r in REMOTE])
def test_remote_commands_follow_the_cross_shell_rule(doc: str, snippet: str, remote: str):
    if remote.startswith('"'):
        assert QUOTED_OK.match(remote), (
            f"{doc}: {snippet!r} — a quoted remote command must be one pair of double quotes "
            "with no $, backtick, %, ! or \" inside (PowerShell and cmd expand them)")
    else:
        # Usage templates such as `camlctl <command> [args]` are placeholders, not shell syntax.
        plain = re.sub(r"<[a-z ]+>|\[[a-z ]+\]", "X", remote)
        assert BARE_OK.match(plain), (
            f"{doc}: {snippet!r} — an unquoted remote command may only hold plain words "
            "(no quotes, ~, $, |, &, ;, <, >, parentheses or globs)")


def _camlctl_commands() -> set[str]:
    text = (ROOT / "scripts" / "camlctl").read_text()
    return set(re.findall(r"^  ([a-z][a-z-]*)\) cmd_", text, re.M))


def test_every_camlctl_command_in_the_docs_exists():
    known = _camlctl_commands() - {"__job"}
    assert {"info", "setup", "caml", "dataset", "start", "wait", "status", "bundle"} <= known
    bad = []
    for doc in AGENT_DOCS:
        for snippet in _code_snippets(doc.read_text()):
            for word in re.findall(r"\bcamlctl\s+([a-z][a-z-]*)\b", snippet):
                if word not in known and word not in {"help", "must"}:  # "camlctl must run as root": an error message
                    bad.append(f"{doc.relative_to(ROOT)}: camlctl {word}  ({snippet})")
    assert not bad, "\n".join(bad)


def test_no_trailing_comments_on_copyable_ssh_lines():
    # zsh doesn't treat `#` as a comment when pasted interactively.
    bad = [f"{d}: {s}" for d, s, r in REMOTE if " #" in r]
    assert not bad, "\n".join(bad)


def _prompts(path: Path) -> dict[str, str]:
    text = path.read_text()
    found = {}
    for slug in OSES:
        m = re.search(rf"<!-- prompt:{slug} -->\n```text\n(.*?)\n```\n<!-- /prompt:{slug} -->", text, re.S)
        assert m, f"{path.name}: no prompt block for {slug}"
        found[slug] = m.group(1)
    return found


def test_readme_prompts_match_the_prompt_doc():
    assert _prompts(README) == _prompts(PROMPT_DOC)


@pytest.mark.parametrize("slug", sorted(OSES))
def test_each_prompt_points_to_its_profile_and_field_report(slug: str):
    prompt = _prompts(PROMPT_DOC)[slug]
    assert f"references/{OSES[slug]}" in prompt
    assert f"caml-field-report-{slug}.md" in prompt
    assert "references/field-report.md" in prompt
    assert "skills/caml-benchmark/SKILL.md" in prompt
    assert "My details" in prompt and "ssh caml-vps camlctl" in prompt
    others = [p for s, p in OSES.items() if s != slug]
    assert not any(o in prompt for o in others), "a prompt names another OS's profile"
    assert "```" not in prompt  # it must fit in one fenced block


@pytest.mark.parametrize("slug", sorted(OSES))
def test_operator_profiles_cover_the_essentials(slug: str):
    text = (REFS / OSES[slug]).read_text()
    for needle in ("ssh -o BatchMode=yes caml-vps echo ok", "## 2. SSH access", "## 3. The quoting rule",
                   "## 4. Local commands", "## 5. Gotchas", "camlctl.md", "tabpfn-token",
                   "Install nothing", "field report"):
        assert needle in text, f"{OSES[slug]} is missing {needle!r}"


def test_skill_links_resolve():
    text = (SKILL / "SKILL.md").read_text()
    for target in set(re.findall(r"\]\((references/[^)#]+)", text)):
        assert (SKILL / target).is_file(), target
    for name in OSES.values():
        assert f"references/{name}" in text


def test_field_report_template_has_the_sections_agents_fill():
    text = (REFS / "field-report.md").read_text()
    for section in ("## Environment", "## Summary", "## Problems", "## Gotchas",
                    "## Docs: wrong, missing or unclear", "## What worked first time", "## Monitoring"):
        assert section in text
    assert (ROOT / ".github" / "ISSUE_TEMPLATE" / "field-report.md").is_file()


def test_versions_agree():
    v = _version()
    assert re.search(rf'^version = "{re.escape(v)}"$', (ROOT / "pyproject.toml").read_text(), re.M)
    assert re.search(rf"^version: {re.escape(v)}$", (ROOT / "CITATION.cff").read_text(), re.M)
    assert re.search(rf'^  version: "{re.escape(v)}"$', (SKILL / "SKILL.md").read_text(), re.M)
    assert json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())["version"] == v
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    assert all(p["version"] == v for p in market["plugins"])
    for doc in (README, SKILL / "SKILL.md"):
        assert f"version = {{{v}}}," in doc.read_text(), doc.name
    lock = (ROOT / "uv.lock").read_text()
    assert re.search(rf'name = "caml"\nversion = "{re.escape(v)}"', lock)
