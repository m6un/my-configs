#!/bin/bash
set -euo pipefail
extension="$(cd -- "$(dirname -- "$0")" && pwd)/extensions/poteto.ts"
scratch=$(mktemp -d)
trap 'rm -rf -- "$scratch"' EXIT
export PI_CODING_AGENT_DIR="$scratch/agent"
mkdir -p "$PI_CODING_AGENT_DIR" "$scratch/poteto-mode/playbooks"
cd "$scratch"
cat > poteto-mode/SKILL.md <<'EOF'
---
name: poteto-mode
description: Fixture for explicit-only pstack skill discovery.
disable-model-invocation: true
---
FULL_MODE_FIXTURE_SHOULD_NOT_BE_INJECTED
EOF
cat > probe.ts <<'EOF'
import assert from "node:assert/strict";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
export default function probe(pi: ExtensionAPI) {
  pi.on("before_agent_start", ({ systemPromptOptions: { sections } }) => {
    try {
      const actual = sections.poteto;
      if (process.env.EXPECT_POTETO === "on") {
        assert.ok(actual?.includes(process.env.EXPECT_PLAYBOOKS!));
        assert.ok(!actual.includes("FULL_MODE_FIXTURE_SHOULD_NOT_BE_INJECTED"));
      } else {
        assert.equal(actual, undefined);
      }
      process.exit(0);
    } catch (error) {
      console.error(error);
      process.exit(1);
    }
  });
}
EOF
run=(pi --offline --no-extensions --no-skills --no-context-files --no-session
  --tools read --model openai/gpt-4o-mini --api-key fixture-only --extension "$extension")
probe=(--extension "$scratch/probe.ts" -p 'Check the mode before any model request.')
export EXPECT_PLAYBOOKS="$scratch/poteto-mode/playbooks"
EXPECT_POTETO=off "${run[@]}" --skill "$scratch/poteto-mode" "${probe[@]}"
"${run[@]}" -p '/poteto on'
EXPECT_POTETO=on "${run[@]}" --skill "$scratch/poteto-mode" "${probe[@]}"
EXPECT_POTETO=off "${run[@]}" "${probe[@]}"
"${run[@]}" -p '/poteto off'
EXPECT_POTETO=off "${run[@]}" --skill "$scratch/poteto-mode" "${probe[@]}"
printf 'Poteto toggle, persistence, and missing-skill behavior passed.\n'
