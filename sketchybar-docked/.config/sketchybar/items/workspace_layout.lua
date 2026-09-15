-- Both AeroSpace bar profiles read the shared, already-applied monitor policy.
return function()
  local mapping = {}
  local command = [[export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin";
    plan=$(cat "$HOME/.local/state/dotfiles-wm/display-layout.json" 2>/dev/null) &&
    displays=$(sketchybar --query displays) &&
    jq -nr --argjson plan "$plan" --argjson displays "$displays" '
      $plan[] as $screen | $displays[] |
      select((.DirectDisplayID // .id) == $screen.id) |
      ."arrangement-id" as $display | $screen.workspaces[] | [.,$display] | @tsv'
  ]]
  local handle = io.popen(command)
  if handle then
    for line in handle:lines() do
      local workspace, display = line:match("^(%d+)%s+(%d+)$")
      if workspace then mapping[tonumber(workspace)] = tonumber(display) end
    end
    handle:close()
  end
  if not next(mapping) then for i = 1, 6 do mapping[i] = 1 end end
  return mapping
end
