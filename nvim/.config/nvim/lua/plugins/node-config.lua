-- Node/TypeScript configuration
-- vtsls automatically uses TypeScript from node_modules/.bin/tsserver
return {
  -- Ensure Mason uses pnpm for installing packages (optional)
  {
    "mason-org/mason.nvim",
    opts = {
      -- Mason installs its own isolated copies of tools
      -- This doesn't affect your project's pnpm/node setup
    },
  },

  -- vtsls settings
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        vtsls = {
          settings = {
            vtsls = {
              -- Automatically use workspace TypeScript version
              autoUseWorkspaceTsdk = true,
            },
          },
        },
      },
    },
  },
}
