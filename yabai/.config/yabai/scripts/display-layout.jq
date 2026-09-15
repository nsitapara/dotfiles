# Input: yabai displays joined with CoreGraphics/NSScreen metadata.
# Known monitor names retain their roles even when macOS changes display order.
map({id,index,uuid,frame,name,builtin}) | sort_by(.frame.x, .frame.y) as $screens |
[$screens[] | select(.builtin)] as $laptop |
[$screens[] | select(.builtin | not)] as $external |
if ($screens | length) < 1 or ($screens | length) > 3
   or ($laptop | length) > 1 or ($external | length) > 2 then
  error("Supported layout: one laptop screen and up to two external monitors")
elif ($screens | length) == 1 then
  [$screens[0] + {workspaces:[1,2,3,4,5,6]}]
elif ($external | length) == 1 then
  [$laptop[0] + {workspaces:[1,3,5]}, $external[0] + {workspaces:[2,4,6]}]
else
  ([$external[] | select(.name == $prefs.odd_monitor)][0] //
   [$external[] | select(.name != $prefs.even_monitor)][0] // $external[0]) as $odd |
  [$external[] | select(.id != $odd.id)][0] as $even |
  [$odd + {workspaces:[1,3,5]}, $even + {workspaces:[2,4,6]}] +
  [$laptop[] | . + {workspaces:[7,8,9]}]
end |
map(. + {top_padding:(if .builtin then $prefs.built_in_top_padding else $prefs.external_top_padding end)}) |
sort_by(.id)
