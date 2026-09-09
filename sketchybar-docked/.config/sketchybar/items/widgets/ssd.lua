local colors = require("colors")
local icons = require("icons")
local settings = require("settings")

local ssd = sbar.add("item", "widgets.ssd", {
  position = "right",
  icon = {
    string = icons.disk,
    padding_left = 8,
    font = { style = settings.font.style_map["Regular"], size = 14.0 },
  },
  label = {
    string = "--%",
    padding_right = 12,
    font = { family = settings.font.numbers },
  },
  padding_left = 5,
  padding_right = 0,
  background = { drawing = true, color = colors.bg1 },
  update_freq = 60,
  click_script = "open -a Finder /",
})

local function update_storage()
  -- APFS volumes share container space. Total minus available includes the
  -- system and sibling volumes, unlike df's per-volume Used/Capacity columns.
  sbar.exec("df -kP /System/Volumes/Data", function(result)
    local total, available = result:match("\n%S+%s+(%d+)%s+%d+%s+(%d+)")
    total, available = tonumber(total), tonumber(available)
    if not total or total <= 0 or not available then
      ssd:set({ label = "--%" })
      return
    end
    local used = math.floor(100 * (total - available) / total + 0.5)
    ssd:set({ label = used .. "%" })
  end)
end

ssd:subscribe({ "routine", "system_woke" }, update_storage)
update_storage()
