// Accounting used by the system_stats SketchyBar provider.
// cc -I sketchybar/.config/sketchybar/helpers/event_providers/system_stats \
//    tests/test_system_stats.c -o /tmp/test-system-stats && /tmp/test-system-stats
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include "stats.h"

static int near(double a, double b) { return fabs(a - b) < 1e-9; }

int main(void) {
  // RAM excludes cache and purgeable pages and counts the compressor's
  // physical size: (600 - 100) + 200 wired + 100 compressor of 1000 pages.
  struct { uint64_t page_size, total_pages; double expected; } memory[] = {
    { 16384, 1000, 0.8 },
    { 4096, 1000, 0.8 },
  };
  for (unsigned i = 0; i < sizeof(memory) / sizeof(memory[0]); i++) {
    double fraction = memory_used_fraction(600, 100, 200, 100, memory[i].page_size,
                                           memory[i].total_pages * memory[i].page_size);
    assert(near(fraction, memory[i].expected));
  }
  assert(memory_used_fraction(600, 100, 200, 100, 16384, 0) == -1);
  assert(memory_used_fraction(600, 100, 200, 100, 0, 1000) == -1);
  assert(near(memory_used_fraction(50, 100, 200, 100, 1, 1000), 0.3)); // purgeable > anonymous
  assert(memory_used_fraction(5000, 0, 0, 0, 1, 1000) == 1);            // clamp

  // Disk space: total minus available, rounded.
  assert(disk_used_percent(1000, 255) == 75);
  assert(disk_used_percent(1000, 1000) == 0);
  assert(disk_used_percent(0, 0) == -1);
  assert(disk_used_percent(1000, 1001) == -1);

  puts("system_stats accounting checks passed");
  return 0;
}
