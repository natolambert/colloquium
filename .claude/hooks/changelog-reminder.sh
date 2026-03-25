#!/bin/bash
# Reminds Claude to update CHANGELOG.md before committing or opening a PR

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if echo "$COMMAND" | grep -qE 'git commit|git push|gh pr create'; then
  echo "Reminder: Update CHANGELOG.md with a one-line summary and PR link before committing." >&2
fi

exit 0
