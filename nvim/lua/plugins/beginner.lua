-- Small, beginner-friendly defaults. AstroNvim remains otherwise stock.
---@type LazySpec
return {
  {
    "AstroNvim/astrocore",
    opts = {
      options = {
        opt = {
          mouse = "a", -- click, scroll, select, and resize with the mouse
          number = true,
          relativenumber = false,
          clipboard = "unnamedplus", -- use the macOS system clipboard
        },
      },
    },
  },
}
