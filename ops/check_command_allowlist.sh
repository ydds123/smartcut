#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ALLOWLIST_FILE="${ALLOWLIST_FILE:-${ROOT_DIR}/ops/command_allowlist.yaml}"

if [[ $# -eq 0 ]]; then
  echo "Usage:"
  echo "  $0 \"npm run dev\""
  echo "  $0 npm run dev"
  exit 2
fi

python3 - "$ALLOWLIST_FILE" "$@" <<'PY'
import ast
import re
import shlex
import sys
from pathlib import Path


def parse_prefixes(text: str, section_key: str) -> list[list[str]]:
    lines = text.splitlines()
    in_section = False
    base_indent = 0
    prefixes: list[list[str]] = []

    for line in lines:
        if re.match(rf"^\s*{re.escape(section_key)}\s*:\s*$", line):
            in_section = True
            base_indent = len(line) - len(line.lstrip())
            continue

        if not in_section:
            continue

        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip())
        if indent <= base_indent and not line.lstrip().startswith("-"):
            break

        match = re.match(r"^\s*-\s*(\[[^\]]*\])\s*$", line)
        if not match:
            continue

        array_literal = match.group(1)
        try:
            value = ast.literal_eval(array_literal)
        except (SyntaxError, ValueError):
            continue

        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            prefixes.append(value)

    return prefixes


def parse_default_policy(text: str) -> str:
    match = re.search(r"^\s*default_policy\s*:\s*([A-Za-z_]+)\s*$", text, re.MULTILINE)
    if not match:
        return "deny"
    return match.group(1).strip().lower()


def matches_prefix(prefix: list[str], command: list[str]) -> bool:
    if len(prefix) > len(command):
        return False
    return command[: len(prefix)] == prefix


allowlist_path = Path(sys.argv[1])
input_args = sys.argv[2:]

if not allowlist_path.exists():
    print(f"ERROR | allowlist_not_found={allowlist_path}", file=sys.stderr)
    sys.exit(2)

allowlist_text = allowlist_path.read_text(encoding="utf-8")
allow_prefixes = parse_prefixes(allowlist_text, "allow_prefixes")
deny_prefixes = parse_prefixes(allowlist_text, "deny_prefixes")
default_policy = parse_default_policy(allowlist_text)

if len(input_args) == 1:
    command_tokens = shlex.split(input_args[0])
else:
    command_tokens = input_args

if not command_tokens:
    print("ERROR | empty_command", file=sys.stderr)
    sys.exit(2)

for prefix in deny_prefixes:
    if matches_prefix(prefix, command_tokens):
        print(
            f"DENY | command={' '.join(command_tokens)} | matched_prefix={' '.join(prefix)}"
        )
        sys.exit(10)

for prefix in allow_prefixes:
    if matches_prefix(prefix, command_tokens):
        print(
            f"ALLOW | command={' '.join(command_tokens)} | matched_prefix={' '.join(prefix)}"
        )
        sys.exit(0)

if default_policy == "allow":
    print(f"ALLOW(default) | command={' '.join(command_tokens)}")
    sys.exit(0)

print(f"REVIEW | command={' '.join(command_tokens)} | reason=prefix_not_listed")
sys.exit(20)
PY
