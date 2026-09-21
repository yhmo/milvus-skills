#!/usr/bin/env bash
set -euo pipefail

for t in ~/.opencode/skills ~/.claude/skills ~/.codex/skills; do
  mkdir -p "$t"
  for d in "$PWD"/*/; do
    case "$(basename "$d")" in
      .git) continue ;;
    esac
    target="$t/$(basename "$d")"
    if [ -e "$target" ] && [ ! -L "$target" ]; then
      echo "skip $target: existing real directory, remove it first" >&2
      continue
    fi
    ln -sfn "$d" "$target"
    echo "linked $d -> $target"
  done
done
