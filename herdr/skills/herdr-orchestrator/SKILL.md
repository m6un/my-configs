---
name: herdr-orchestrator
description: Orchestrate coding work through visible Herdr agents in isolated Git worktrees. Use when the user asks for Herdr delegation, parallel coding, an orchestrator/worker workflow, or review-first delivery through feature branches, PRs, CI, and cleanup. Keeps implementation workers visible and changes uncommitted until approval.
---

# Herdr orchestrator

## Roles and boundaries

- Main agent owns planning, delegation, monitoring, diff review, verification, and handoff. Workers implement.
- Read global and project AGENTS.md and relevant project docs first. Project-specific checks and approval rules apply.
- Use `start_herdr_worktree_agent`; never substitute hidden subagents for worktree workers.
- Default implementation workers to `opencode-go` (OpenCode Go).
- See the Model routing section below; explicit user model choice always wins.
- Keep implementation agents separate from user-facing test agents. A test agent editing a diagram is not a repository implementation worker. Do not repurpose or interrupt user test panes.
- Observations during UX testing are findings, not automatic authorization for unrelated code changes.

## 1. Inspect and plan

- Inspect the current branch, dirty files, worktrees, and existing Herdr agents before starting anything. Preserve user work.
- Establish scope, acceptance criteria, relevant callers, and the required checks.
- Split work by narrow ownership. Parallelize only independent tasks; serialize changes to shared files or dependent behavior.
- For uncertain bug fixes, stage the work: reproduce and capture failures → review evidence → fix root causes → regression checks and visual QA where relevant.
- Do not build a framework merely to coordinate agents.

## 2. Start a visible worker

Call `start_herdr_worktree_agent` with a unique `agent/<task>` branch, agent name, model, thinking level, and task. Record the returned branch, worktree path, tab, and pane; never assume paths or reuse old pane IDs.

Worker task template:

```text
Goal: <specific outcome>
Read: AGENTS.md and <relevant docs/source>
Own: <files/subsystem>; do not change <excluded scope>
Acceptance: <observable behavior and regression checks>
Stage/checkpoint: <where to stop for orchestrator review>
Validation: <project commands and manual checks>
Keep changes uncommitted. Do not push, merge, or publish.
Report changed files, checks, failures, known limitations, and blockers.
Generate .hunk/agent-context.json from the final diff before handoff.
```

If the start tool is unavailable, report the missing capability instead of silently switching to hidden workers. Consult `herdr ... --help` for unfamiliar CLI operations.

## 3. Model routing

The orchestrator model is user-selected and currently **GPT-5.6 Sol**. Provisional implementation-worker defaults:

| Task | Model | Thinking |
|---|---|---|
| Docs, config, mechanical edits | `glm-5.3-flash` | low/off |
| Normal coding; initial hard-algorithm work | `kimi-k2.7-code` | medium |
| Large-context / repository investigation | `deepseek-v4-flash` or `qwen3.7-plus` | medium |
| Images | `deepseek-v4-flash-vision-exp` or `glm-5.3-flash` | — |
| Challengers/escalations only | `glm-5.3`, `qwen3.8-max`, `deepseek-v4-pro` | — |

- `muse-spark-1.3-contributor` is allowed despite training caveats; the user accepts that for intended open-source work.
- Premium models are challengers/escalations, never first defaults.
- Availability drifts: query `pi --list-models opencode-go` (or the relevant model id) instead of assuming catalog permanence.
- Strict secret handling applies to every model; routing never relaxes it.

### Adaptive switching

Do not switch on one ordinary mistake; redirect once with concrete evidence first. Switch when a worker shows:

- repeated compile/test failures after correction
- scope drift, weakened tests, or unsupported claims
- tool loops or inability to follow a correction
- context-limit, provider, or rate-limit failures
- clearly poor diff quality

To switch: preserve the worktree, stop the old agent safely, start a new visible agent in the same pane with a concise handoff to inspect the current diff, then rearm the wake listener. Record the model and reasoning level in the status ledger. Explicit user model choice wins over all routing rules.

### Automatic outcome tracking

After reviewing each worker stage, run [scripts/model_outcome.py](scripts/model_outcome.py) yourself — do not ask the worker and do not ask the user. It stores outcomes by default at `~/.pi/agent/state/herdr-model-outcomes.jsonl` (outside git) and records only UTC timestamp, model, thinking level, task category, green/yellow/red, redirect count, and a short reason code. Never record prompts, source, paths, secrets, or freeform text.

```bash
# record (after diff review): green = no material correction,
# yellow = one successful correction, red = repeated material failure / unusable diff
python3 .../scripts/model_outcome.py record --model <model> --thinking <lvl> \
  --category <coding|docs|mechanical|algorithm|investigate|images> \
  --outcome <green|yellow|red> [--redirects <n>] --reason <code>

# before the next assignment, ask for a verdict: current = model,
# recommended_model = model to use next; fallback is escalation-only
python3 .../scripts/model_outcome.py decision --model <model> \
  --category <cat> --outcome <red> --reason <code>

python3 .../scripts/model_outcome.py --self-test   # temp-storage self-check
```

Verdict rules:

- `switch` immediately on provider/rate/context-limit/tool-protocol failure (`--reason provider_fail|rate_limit|context_limit|tool_protocol`).
- otherwise a red outcome gets exactly one redirect on the **same** model (`redirect_once`, `recommended_model` = current); switch only if the redirect also fails or the same model has 2 reds among its last 3 stages in that category.
- `continue` (green/yellow) always keeps the current model as `recommended_model`, even when it is not the category default; `fallback` is escalation-only and never assigned preemptively.

On a `switch` verdict use `recommended_model` as the prescribed category fallback (same policy for immediate-switch); on `redirect_once`/`continue` keep the current model (`recommended_model` = current). In either switch path, preserve the worktree, stop the old agent safely, start a new visible agent in the same pane with a concise handoff to inspect the current diff, and rearm the wake listener. Switching models never authorizes commit/merge. Ask the user only when all fallbacks fail or an explicit user model choice conflicts. The script is no daemon; each call exits.

## 4. Monitor and steer

Use the returned agent name or pane ID:

```bash
herdr agent read <agent> --source recent-unwrapped --lines 120
herdr agent wait <agent> --timeout 120000
herdr agent prompt <agent> "<narrow correction or next stage>"
```

### Automatic wake-ups (default for delegated stages)

Use [scripts/worker_wakeup.py](scripts/worker_wakeup.py), a Python-stdlib one-shot bridge between Herdr's native socket subscriptions and `herdr agent prompt`. It is custom glue, not a Herdr service. Resolve the script path relative to this skill directory.

After submitting a stage, confirm the worker has started using `agent get`/`agent read` (or a bounded `agent wait --until working`). If it already finished, review it directly. Do not arm against a pre-submission idle worker. Start one listener per worker/stage:

```bash
python3 - /absolute/path/to/scripts/worker_wakeup.py <worker-pane-id> "$HERDR_PANE_ID" <<'PY'
import os, subprocess, sys, tempfile
script, worker, origin = sys.argv[1:]
fd, log_path = tempfile.mkstemp(prefix="herdr-wakeup-", suffix=".log")
with os.fdopen(fd, "w") as log:
    process = subprocess.Popen(
        [sys.executable, "-u", script, worker, origin],
        stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True, cwd=os.path.dirname(script),
    )
print(f"Listener PID={process.pid} log={log_path}")
PY
```

- Record PID, log path, worker pane, and stage in the status ledger. Read the log to confirm `Subscribed` and inspect process liveness; do not claim monitoring is armed merely because a process was spawned.
- The listener subscribes before checking current state, then sends one fixed lifecycle notification on `idle`, `done`, or `blocked` and exits. The snapshot catches completion during startup. It verifies the original orchestrator session before delivery.
- When notified, read the worker report, inspect its diff, and run checks. Events do not prove completion or authorize commits/merges. A `blocked` notification requires inspection, not automatic approval.
- Rearm after each new delegated stage. Do not start duplicate listeners or let notifications recursively rearm without new work.
- On cancellation/cleanup, verify the recorded PID's command still matches this worker's listener, then terminate only that process. Never kill by broad process-name matching or stale PID alone.
- Disconnects, delivery errors, and four hours without an event cause the listener to exit; inspect its log and fall back to `agent wait/read`. It does not reconnect automatically or survive machine restart. Check listener health when resuming a conversation.
- The bridge delivers through the pane's agent input, not a private Pi RPC queue. Avoid typing manually into the orchestrator input while expecting automated delivery.
- Validate the helper with `python3 /absolute/path/to/scripts/worker_wakeup.py --self-test`. Inspect installed API metadata with `herdr api schema --json` if the protocol changes.

- Inspect progress after startup, at checkpoints, and after failed checks. A timeout is a reason to read progress, not evidence of failure.
- Do not accept idle/done status as proof of completion: read the report and inspect the actual diff.
- Redirect scope drift, speculative abstractions, symptom patches, weakened tests, or accidental shared-file changes promptly.
- Stop and inspect on a user cancellation. Revert only the canceled task's changes; preserve all prior work. Never broadly reset a dirty worktree.
- Keep a compact status ledger in the conversation: owner, branch/path/pane, stage, blockers, checks, next action.

## 5. Review and verify

- Inspect tracked changes and untracked files. Check the complete branch diff against its base, not just the last edit.
- Review root-cause correctness, affected callers, error handling, and scope. A passing test suite alone does not establish visual correctness.
- Run project checks from the worker worktree. For Diaview: format, tests, check, strict Clippy, and renderer inspection as appropriate.
- A diagnostic that records a known failure is not a passing correctness regression. Resolve or explicitly disclose skipped/ignored tests before declaring completion.
- Generate the ignored `.hunk/agent-context.json` from the final diff using exactly this version-1 shape:

```json
{"version":1,"summary":"...","files":[{"path":"src/example.rs","summary":"...","annotations":[{"newRange":[1,2],"summary":"...","rationale":"...","author":"..."}]}]}
```

Use `oldRange` for deleted lines. Do not commit this sidecar.

- Leave implementation uncommitted for Neovim review. Open a visible review pane when available/requested, without replacing the user's test setup.
- Report what changed, checks actually run, remaining limitations, and the review path. Wait for approval.

## 6. Approved delivery

- Confirm approval covers committing/pushing/merging; creating a worker is not approval to publish changes.
- Stage only intended files and commit on the feature branch. Exclude review sidecars and local artifacts.
- Push the feature branch and open a PR against the intended base. Do not push directly to main.
- Wait for GitHub Actions on the current PR head. Fix failures on the feature branch and re-review any changes; never bypass CI to land a fix.
- Merge only after required checks pass and the user has authorized merge.
- Tags, package publication, and GitHub releases require separate approval.

## 7. Clean up after merge

- Confirm the PR merged and record its merge commit.
- Ensure the worker has stopped writing and there is no unmerged or user-owned work in its worktree.
- Stop any remaining listener for this task using its recorded PID after verifying its command and worker target.
- Close only the worker/review panes created for that task; preserve user test sessions.
- Update the target checkout safely (fast-forward when appropriate), remove the merged worktree, and delete the merged local/remote feature branch.
- Never use force removal to discard unexplained dirty files. Inspect and preserve them first.
- Verify the target checkout status and remaining worktrees/refs. Report merge/CI/cleanup status and any explicit follow-up work.
