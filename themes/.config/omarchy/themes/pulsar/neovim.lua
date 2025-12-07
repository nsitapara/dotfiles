-- Pulsar theme for Neovim
-- Uses tokyonight-night as a close match for the neon/cyberpunk aesthetic
return {
	{
		"LazyVim/LazyVim",
		opts = {
			colorscheme = "tokyonight-night",
		},
	},
	{
		"folke/tokyonight.nvim",
		opts = {
			style = "night",
			transparent = false,
			terminal_colors = true,
		},
	},
}
