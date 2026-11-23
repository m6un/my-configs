local function hunk(args)
  if vim.fn.executable "hunk" == 0 then
    vim.notify("hunk is not installed", vim.log.levels.ERROR)
    return
  end

  local cwd = vim.fs.root(0, { ".git", ".jj" }) or vim.fn.getcwd()
  local context = vim.fs.joinpath(cwd, ".hunk", "agent-context.json")
  if args[1] == "diff" and vim.uv.fs_stat(context) then
    vim.list_extend(args, { "--agent-context", context })
  end

  vim.cmd.enew()

  local buffer = vim.api.nvim_get_current_buf()
  vim.bo[buffer].bufhidden = "wipe"

  vim.fn.jobstart(vim.list_extend({ "hunk" }, args), {
    cwd = cwd,
    term = true,
    on_exit = function()
      vim.schedule(function()
        if vim.api.nvim_buf_is_valid(buffer) then vim.api.nvim_buf_delete(buffer, { force = true }) end
      end)
    end,
  })
  vim.keymap.set("t", "<Space>", [[<C-\><C-n><Plug>(HunkLeader)]], { buffer = buffer })
  vim.keymap.set("n", "<Plug>(HunkLeader)", function()
    -- which-key's cursor avoidance can clip the menu against Hunk's bottom row.
    local win = require("which-key.config").win
    local no_overlap = win.no_overlap
    win.no_overlap = false
    local ok, err = pcall(require("which-key").show, { keys = "<Space>", mode = "n" })
    win.no_overlap = no_overlap
    -- Run after which-key's queued shortcut, and only if it leaves focus in Hunk.
    vim.api.nvim_feedkeys(vim.keycode "<Plug>(HunkResume)", "m", false)
    if not ok then vim.notify(tostring(err), vim.log.levels.ERROR) end
  end, { buffer = buffer, desc = "Open Neovim leader menu" })
  vim.keymap.set("n", "<Plug>(HunkResume)", "<Cmd>startinsert<CR>", { buffer = buffer })
  vim.api.nvim_create_autocmd("BufEnter", { buffer = buffer, command = "startinsert" })
  vim.cmd.startinsert()
end

---@type LazySpec
return {
  "AstroNvim/astrocore",
  opts = {
    mappings = {
      n = {
        ["<Leader>gd"] = { function() hunk { "diff", "--watch" } end, desc = "Review working-tree changes" },
        ["<Leader>gD"] = { function() hunk { "diff", "--staged", "--watch" } end, desc = "Review staged changes" },
        ["<Leader>gh"] = { function() hunk { "show" } end, desc = "Review last commit" },
      },
    },
  },
}
