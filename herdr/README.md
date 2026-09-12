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

Requirements: Python 3 and the `herdr` CLI on `PATH`.

## Self-test

```sh
python3 herdr/skills/herdr-orchestrator/scripts/worker_wakeup.py --self-test
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
from pathlib import Path
compile(Path('herdr/skills/herdr-orchestrator/scripts/worker_wakeup.py').read_text(), 'worker_wakeup.py', 'exec')
print('syntax ok')
PY
```
