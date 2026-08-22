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
