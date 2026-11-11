// One provider for the CPU, memory, SSD and temperature widgets: reads every
// value straight from the kernel and fires a single SketchyBar event, so no
// sensor commands are spawned and the graphs move together.
//
// Usage: system_stats <event-name> <seconds>
// Event variables (-1 = unavailable):
//   cpu   total CPU load, percent
//   mem   used memory, percent (one decimal)
//   temp  CPU die average (SMC key TCMb), degrees Celsius
// Only on the first tick, every 5 minutes and after wake:
//   disk  used disk space, percent
#include <IOKit/IOKitLib.h>
#include <mach/mach.h>
#include <sys/mount.h>
#include <sys/sysctl.h>
#include <time.h>
#include "cpu.h"
#include "smc.h"
#include "stats.h"
#include "../sketchybar.h"

#define DISK_SPACE_SECONDS 300.0

// Build with -DSTATS_PRINT to print events instead of sending them.
static void emit(char* message) {
#ifdef STATS_PRINT
  puts(message);
  fflush(stdout);
#else
  sketchybar(message);
#endif
}

static double monotonic_seconds(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
  return ts.tv_sec + ts.tv_nsec / 1e9;
}

static double memory_percent(host_t host, uint64_t total_bytes) {
  vm_statistics64_data_t vm;
  mach_msg_type_number_t count = HOST_VM_INFO64_COUNT;
  if (host_statistics64(host, HOST_VM_INFO64, (host_info64_t)&vm, &count) != KERN_SUCCESS)
    return -1;
  vm_size_t page_size = 0;
  if (host_page_size(host, &page_size) != KERN_SUCCESS) return -1;
  double fraction = memory_used_fraction(vm.internal_page_count, vm.purgeable_count,
                                         vm.wire_count, vm.compressor_page_count,
                                         page_size, total_bytes);
  return fraction < 0 ? -1 : fraction * 100.0;
}

static int disk_space_percent(void) {
  struct statfs fs;
  if (statfs("/System/Volumes/Data", &fs) != 0) return -1;
  return disk_used_percent(fs.f_blocks, fs.f_bavail);
}

int main(int argc, char** argv) {
  float interval;
  if (argc < 3 || sscanf(argv[2], "%f", &interval) != 1 || interval <= 0) {
    printf("Usage: %s \"<event-name>\" \"<seconds>\"\n", argv[0]);
    exit(1);
  }
  // SbarLua puts a 60-second alarm on exec children; this one runs forever.
  alarm(0);

  host_t host = mach_host_self();
  uint64_t total_memory = 0;
  size_t size = sizeof(total_memory);
  sysctlbyname("hw.memsize", &total_memory, &size, NULL, 0);

  struct cpu cpu;
  cpu_init(&cpu);
  struct smc smc;
  smc_init(&smc, "TCMb");

  char message[512];
  snprintf(message, sizeof(message), "--add event '%s'", argv[1]);
  emit(message);

  // Prime the CPU counters so the first event carries a real load.
  cpu_update(&cpu);
  double previous_time = monotonic_seconds();
  usleep(1000000);

  bool has_disk = false;
  double disk_time = 0;
  for (;;) {
    double now = monotonic_seconds();
    cpu_update(&cpu);
    // A gap well past the interval means the Mac slept: refresh disk space too.
    bool woke = now - previous_time > interval * 3;
    previous_time = now;

    int length = snprintf(message, sizeof(message),
                          "--trigger '%s' cpu='%d' mem='%.1f' temp='%.1f'",
                          argv[1], cpu.total_load, memory_percent(host, total_memory),
                          smc_temperature(&smc));
    // Disk space changes slowly; send it only when re-read, so the SSD
    // widget and its graph update every 5 minutes, not every tick.
    if (!has_disk || woke || now - disk_time >= DISK_SPACE_SECONDS) {
      int disk = disk_space_percent();
      has_disk = disk >= 0;
      disk_time = now;
      snprintf(message + length, sizeof(message) - length, " disk='%d'", disk);
    }
    emit(message);
    usleep((useconds_t)(interval * 1000000));
  }
  return 0;
}
