# Herdr skill glue

This directory stores our custom `herdr-orchestrator` skill and its one-shot wake-up helper. The helper is small glue over native Herdr socket events; it is not a daemon, listener service, or replacement for `herdr agent wait/read/prompt`.

## Install

```sh
mkdir -p ~/.pi/agent/skills/herdr-orchestrator
cp -R herdr/skills/herdr-orchestrator/. ~/.pi/agent/skills/herdr-orchestrator/
```

Do not edit live skill files while testing here; copy them only when you mean to install.

## Use

In Pi, load it with:

```text
/skill:herdr-orchestrator
```

Requirements: Python 3, `herdr`, and Antigravity CLI (`agy`) on `PATH`.

Implementation workers run as visible `agy` sessions in isolated Herdr worktrees. The skill uses Antigravity's configured default model unless the user explicitly requests another model or effort level. Workers are started with `--mode accept-edits --dangerously-skip-permissions`; `--effort low` is not passed because the current default model does not support it.

**Diaview projects (macOS):** also requires the [mbx](https://github.com/jdx/mr-boxington) Cargo shim installed at `$HOME/Library/Application Support/mbx/bin`. The orchestrator verifies the shim and runs `mbx setup --status` before creating the tab, then passes `--env PATH=<mbx-bin>:$PATH` to `herdr tab create`. See the skill's §3a.

## Self-test

```sh
python3 herdr/skills/herdr-orchestrator/scripts/worker_wakeup.py --self-test
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
from pathlib import Path
compile(Path('herdr/skills/herdr-orchestrator/scripts/worker_wakeup.py').read_text(), 'worker_wakeup.py', 'exec')
print('syntax ok')
PY
```
