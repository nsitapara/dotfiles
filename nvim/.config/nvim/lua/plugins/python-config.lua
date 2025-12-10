-- Python configuration for uv-managed projects
return {
  {
    "linux-cultist/venv-selector.nvim",
    opts = {
      settings = {
        search = {
          -- Search for uv-created .venv directories
          project_venvs = {
            command = "fd -H -I -a -td --max-depth 3 '.venv' .",
          },
        },
      },
    },
  },

  -- Configure pyright to use the correct python path
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        pyright = {
          settings = {
            python = {
              -- Pyright will auto-detect .venv in project root
              -- For manual override, uncomment and set:
              -- pythonPath = ".venv/bin/python",
            },
          },
        },
      },
    },
  },
}
