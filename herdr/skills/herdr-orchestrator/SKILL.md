---
name: herdr-orchestrator
description: Orchestrate coding work through visible Herdr agents in isolated Git worktrees. Use when the user asks for Herdr delegation, parallel coding, an orchestrator/worker workflow, or review-first delivery through feature branches, PRs, CI, and cleanup. Keeps implementation workers visible and changes uncommitted until approval.
---

# Herdr orchestrator

## Roles and boundaries

- Main agent owns planning, delegation, monitoring, diff review, verification, and handoff. Workers implement.
- Read global and project AGENTS.md and relevant project docs first. Project-specific checks and approval rules apply.
- Use visible Antigravity CLI workers (`agy`) in Herdr panes; never substitute hidden subagents or Pi/OpenCode workers.
- Use Antigravity's configured default model unless the user explicitly requests a model or effort level.
- Keep implementation agents separate from user-facing test agents. A test agent editing a diagram is not a repository implementation worker. Do not repurpose or interrupt user test panes.
- Observations during UX testing are findings, not automatic authorization for unrelated code changes.

## 1. Inspect and plan

- Inspect the current branch, dirty files, worktrees, and existing Herdr agents before starting anything. Preserve user work.
- Establish scope, acceptance criteria, relevant callers, and the required checks.
- Split work by narrow ownership. Parallelize only independent tasks; serialize changes to shared files or dependent behavior.
- For uncertain bug fixes, stage the work: reproduce and capture failures → review evidence → fix root causes → regression checks and visual QA where relevant.
- Do not build a framework merely to coordinate agents.

## 2. Start a visible worker

Create a unique `agent/<task>` branch in an isolated Git worktree, create a visible Herdr tab rooted there, and start Antigravity CLI with `herdr agent start --kind agy`. Do not use `start_herdr_worktree_agent`; it starts a Pi worker rather than the required Antigravity worker. Record the branch, worktree path, tab, and pane returned by the commands; never assume paths or reuse old pane IDs.

Typical sequence:

```bash
git worktree add -b agent/<task> <absolute-worktree-path> <base-branch>
herdr tab create --cwd <absolute-worktree-path> --label <task> --no-focus
herdr agent start <worker-name> --kind agy --pane <pane-id> -- --mode accept-edits --dangerously-skip-permissions
herdr agent prompt <worker-name> "<task prompt>"
```

Use Antigravity's configured default model. Pass `--model` or a higher `--effort` only when the user explicitly asks or a concrete blocker justifies it.

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

If `agy` or Herdr cannot start, report the blocker instead of silently switching to Pi, OpenCode, or a hidden worker. Consult `agy --help` and `herdr ... --help` for unfamiliar operations.

## 3. Antigravity worker policy

- Antigravity CLI (`agy`) is the only default implementation-worker runtime.
- Start with `--mode accept-edits --dangerously-skip-permissions` and Antigravity's configured default model so isolated worktree workers do not block on every shell command. Do not pass `--effort low`; the current default model does not support that flag.
- Explicit user choices for model, agent, mode, or effort always win.
- Increase effort only after identifying a specific blocker and only for a bounded stage.
- On an ordinary mistake, redirect once with concrete evidence.
- On repeated bad edits, provider failure, context failure, or tool failure, preserve the worktree and restart a fresh visible `agy` session with a concise handoff. Do not fall back to Pi or OpenCode without explicit user approval.
- Strict secret handling applies to every worker and model.

## 3a. Diaview worker tabs — mbx Cargo shim (macOS)

Diaview uses [mbx](https://github.com/jdx/mr-boxington) to provide a per-worktree shared Rust build cache through a Cargo shim. For a **Diaview** task on this macOS setup:

1. **Verify in the orchestrator** before creating the tab:
   ```bash
   MBX_BIN="$HOME/Library/Application Support/mbx/bin"
   test -x "${MBX_BIN}/cargo" && echo "shim ok" || echo "MISSING: install mbx"
   mbx setup --status
   ```
   If either check fails, stop and report the blocker; do not start the worker.

2. **Create the tab** with the shim prepended:
   ```bash
   herdr tab create --cwd <absolute-worktree-path> --label <task> --no-focus \
     --env "PATH=${MBX_BIN}:${PATH}"
   ```

Workers run ordinary `cargo` commands unchanged; the shim routes them through the shared cache. Do not set a shared `CARGO_TARGET_DIR` (mbx manages per-worktree targets). Do not combine mbx with sccache. Non-Diaview workers: omit this section and use the generic sequence from §2.

## 4. Monitor and steer

Use the returned agent name or pane ID for reads, corrections, and next-stage prompts:

```bash
herdr agent read <agent> --source recent-unwrapped --lines 120
herdr agent prompt <agent> "<narrow correction or next stage>"
```

`herdr agent prompt` is asynchronous by default; do **not** use `--wait` or repeated bounded `herdr agent wait` calls as the normal monitoring mechanism. The standard pattern is: prompt asynchronously → confirm the worker reached `working` state via `agent get`/`agent read` → arm `worker_wakeup.py` → receive the lifecycle notification when done. Use `agent wait` only for startup diagnostics (confirming a worker reached `working` before arming) or when the listener has exited and you need a bounded fallback poll.

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

- Execution discipline: architecture, trade-off decisions, and planning belong to the orchestrator. Workers edit, test, and report. If a worker narrates or replans without making checkpoint progress, redirect once to a short concrete edit/check checkpoint; if it still makes no progress, preserve the worktree and restart a fresh visible `agy` session with a concise handoff.
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
