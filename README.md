# my-configs

Personal terminal and editor configuration.

## Neovim

Requires Neovim, Git, and (for the Hunk review mappings) the `hunk` CLI on `PATH`.

```sh
git clone https://github.com/m6un/my-configs.git ~/Projects/my-configs
mv ~/.config/nvim ~/.config/nvim.bak 2>/dev/null || true
ln -s ~/Projects/my-configs/nvim ~/.config/nvim
nvim
```

AstroNvim plugins install on first launch.

Hunk mappings:

- `<Leader>gd`: review working-tree changes and load `.hunk/agent-context.json` when present
- `<Leader>gD`: review staged changes
- `<Leader>gh`: review the last commit

## Pi: Sticky Poteto Mode

Requires Pi 1.4+ and the [pstack skills](https://github.com/backnotprop/pstack) installed in Pi.

```sh
mkdir -p ~/.pi/agent/extensions
ln -s ~/Projects/my-configs/pi/extensions/poteto.ts ~/.pi/agent/extensions/poteto.ts
```

Run `/reload` in Pi, then `/poteto on`. The setting persists across reloads and new sessions. Use `/poteto status` to check it or `/poteto off` to turn it off. While on, Pi adds a short router to the system prompt. The model reads individual playbooks from your existing pstack install as needed. `/skill:poteto-mode` still loads the full skill explicitly.

Run `bash pi/check-poteto.sh` to verify the toggle and prompt injection in an isolated Pi configuration.
