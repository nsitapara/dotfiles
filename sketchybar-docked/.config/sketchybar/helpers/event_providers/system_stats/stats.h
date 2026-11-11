#pragma once
#include <stdint.h>

// Pure accounting shared by the provider and its test.

// App + wired + compressed RAM as a fraction of physical memory, excluding
// reclaimable file cache and purgeable pages. Counts the compressor's physical
// size (compressor_page_count), not the pages stored in it. Returns -1 when the
// inputs can't produce a reading.
static inline double memory_used_fraction(uint64_t anonymous, uint64_t purgeable,
                                          uint64_t wired, uint64_t compressor,
                                          uint64_t page_size, uint64_t total_bytes) {
  if (total_bytes == 0 || page_size == 0) return -1;
  uint64_t pages = (anonymous > purgeable ? anonymous - purgeable : 0)
                   + wired + compressor;
  double fraction = (double)pages * (double)page_size / (double)total_bytes;
  return fraction > 1 ? 1 : fraction;
}

// APFS volumes share container space, so used = total - available covers the
// system and sibling volumes too (df's total minus Available, not Used).
static inline int disk_used_percent(uint64_t blocks, uint64_t available) {
  if (blocks == 0 || available > blocks) return -1;
  return (int)((double)(blocks - available) / (double)blocks * 100.0 + 0.5);
}

// Throughput in MiB/s between two cumulative byte counters, as iostat reports.
static inline double disk_mib_per_second(uint64_t previous, uint64_t current,
                                         double seconds) {
  if (seconds <= 0 || current < previous) return -1;
  return (double)(current - previous) / seconds / 1048576.0;
}
