# Input: yabai displays joined with CoreGraphics/NSScreen metadata.
# Known monitor names retain their roles even when macOS changes display order.
# $profile pins a layout (auto, docked, single, laptop). A pin the connected
# screens cannot satisfy falls back to auto. Every entry names the layout applied.
map({id,index,uuid,frame,name,builtin}) | sort_by(.frame.x, .frame.y) as $screens |
[$screens[] | select(.builtin)] as $laptop |
[$screens[] | select(.builtin | not)] as $external |
([$external[] | select(.name == $prefs.odd_monitor)][0] //
 [$external[] | select(.name != $prefs.even_monitor)][0] // $external[0]) as $odd |
[$external[] | select(.id != $odd.id)][0] as $even |
if ($screens | length) < 1 or ($screens | length) > 3
   or ($laptop | length) > 1 or ($external | length) > 2 then
  error("Supported layout: one laptop screen and up to two external monitors")
elif $profile == "laptop" and ($laptop | length) == 1 then
  [$laptop[0] + {workspaces:[1,2,3,4,5,6], profile:"laptop"}] +
  [$external[] | . + {workspaces:[], profile:"laptop"}]
elif $profile == "single" and ($laptop | length) == 1 and ($external | length) >= 1 then
  [$laptop[0] + {workspaces:[1,3,5], profile:"single"}, $odd + {workspaces:[2,4,6], profile:"single"}] +
  [$external[] | select(.id != $odd.id) | . + {workspaces:[], profile:"single"}]
elif ($screens | length) == 1 then
  [$screens[0] + {workspaces:[1,2,3,4,5,6], profile:"laptop"}]
elif ($external | length) == 1 then
  [$laptop[0] + {workspaces:[1,3,5], profile:"single"}, $external[0] + {workspaces:[2,4,6], profile:"single"}]
else
  [$odd + {workspaces:[1,3,5], profile:"docked"}, $even + {workspaces:[2,4,6], profile:"docked"}] +
  [$laptop[] | . + {workspaces:[7,8,9], profile:"docked"}]
end |
map(. + {top_padding:(if .builtin then $prefs.built_in_top_padding else $prefs.external_top_padding end)}) |
sort_by(.id)
