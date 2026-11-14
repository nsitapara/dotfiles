-- One native provider samples CPU, memory, disk space and temperature and
-- fires "system_stats" for all four stats widgets: CPU, memory and temperature
-- every 2 seconds, disk space every 5 minutes and after wake. It replaces the
-- older cpu_load provider, so stop a leftover one too.
sbar.add("event", "system_stats")
sbar.exec("killall cpu_load system_stats >/dev/null 2>&1; "
  .. "exec $CONFIG_DIR/helpers/event_providers/system_stats/bin/system_stats system_stats 2.0")

require("items.widgets.keep_awake")
require("items.display_profile")
require("items.widgets.battery")
require("items.widgets.volume")
require("items.widgets.memory")
require("items.widgets.cpu")
require("items.widgets.temperature")
require("items.widgets.ssd")
require("items.widgets.codexbar")
require("items.widgets.dev_stacks")
