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
