// One provider for the CPU, memory, SSD and temperature widgets: reads every
// value straight from the kernel each tick and fires a single SketchyBar event,
// so no sensor commands are spawned and all graphs move together.
//
// Usage: system_stats <event-name> <seconds> [<disk-seconds>]
// Event variables (-1 = unavailable):
//   cpu        total CPU load, percent
//   mem        used memory, percent (one decimal)
//   temp       CPU die average (SMC key TCMb), degrees Celsius
// Only every <disk-seconds> (default: every tick):
//   disk       used disk space, percent (refreshed every 5 minutes and on wake)
//   disk_mbps  disk0 read + write throughput since the last disk tick, MiB/s
#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/IOKitLib.h>
#include <IOKit/IOBSD.h>
#include <IOKit/storage/IOBlockStorageDriver.h>
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

// The IOBlockStorageDriver above disk0's whole-disk media, as iostat uses.
static io_service_t disk_driver(void) {
  io_service_t media = IOServiceGetMatchingService(
      kIOMainPortDefault, IOBSDNameMatching(kIOMainPortDefault, 0, "disk0"));
  if (!media) return 0;
  io_registry_entry_t parent = 0;
  kern_return_t error = IORegistryEntryGetParentEntry(media, kIOServicePlane, &parent);
  IOObjectRelease(media);
  if (error != KERN_SUCCESS) return 0;
  if (!IOObjectConformsTo(parent, "IOBlockStorageDriver")) {
    IOObjectRelease(parent);
    return 0;
  }
  return parent;
}

static bool dictionary_u64(CFDictionaryRef dictionary, CFStringRef key, uint64_t* value) {
  CFNumberRef number = CFDictionaryGetValue(dictionary, key);
  return number && CFGetTypeID(number) == CFNumberGetTypeID()
         && CFNumberGetValue(number, kCFNumberSInt64Type, value);
}

static bool disk_bytes(io_service_t* driver, uint64_t* bytes) {
  if (!*driver) *driver = disk_driver();
  if (!*driver) return false;
  CFTypeRef stats = IORegistryEntryCreateCFProperty(
      *driver, CFSTR(kIOBlockStorageDriverStatisticsKey), kCFAllocatorDefault, 0);
  if (!stats) {
    // The driver can be replaced across sleep; look it up again next tick.
    IOObjectRelease(*driver);
    *driver = 0;
    return false;
  }
  uint64_t read = 0, written = 0;
  bool ok = CFGetTypeID(stats) == CFDictionaryGetTypeID()
            && dictionary_u64(stats, CFSTR(kIOBlockStorageDriverStatisticsBytesReadKey), &read)
            && dictionary_u64(stats, CFSTR(kIOBlockStorageDriverStatisticsBytesWrittenKey), &written);
  CFRelease(stats);
  if (ok) *bytes = read + written;
  return ok;
}

int main(int argc, char** argv) {
  float interval, disk_interval;
  if (argc < 3 || sscanf(argv[2], "%f", &interval) != 1 || interval <= 0) {
    printf("Usage: %s \"<event-name>\" \"<seconds>\" [\"<disk-seconds>\"]\n", argv[0]);
    exit(1);
  }
  if (argc < 4 || sscanf(argv[3], "%f", &disk_interval) != 1 || disk_interval < interval)
    disk_interval = interval;
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
  io_service_t driver = 0;

  char message[512];
  snprintf(message, sizeof(message), "--add event '%s'", argv[1]);
  emit(message);

  // Prime the CPU and disk counters so the first event carries real rates.
  cpu_update(&cpu);
  uint64_t previous_bytes = 0;
  bool has_bytes = disk_bytes(&driver, &previous_bytes);
  double previous_time = monotonic_seconds();
  double disk_time = previous_time;
  usleep(1000000);

  int disk_space = -1;
  double disk_space_time = 0;
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

    // Disk fields ride along only on disk ticks, so the SSD graph (which
    // redraws its whole history) updates at its own, slower pace.
    if (woke || now - disk_time >= disk_interval - interval / 2) {
      double mbps = -1;
      uint64_t bytes = 0;
      if (disk_bytes(&driver, &bytes)) {
        if (has_bytes) mbps = disk_mib_per_second(previous_bytes, bytes, now - disk_time);
        previous_bytes = bytes;
        has_bytes = true;
      } else {
        has_bytes = false;
      }
      disk_time = now;
      if (disk_space < 0 || woke || now - disk_space_time >= DISK_SPACE_SECONDS) {
        disk_space = disk_space_percent();
        disk_space_time = now;
      }
      snprintf(message + length, sizeof(message) - length,
               " disk='%d' disk_mbps='%.2f'", disk_space, mbps);
    }
    emit(message);
    usleep((useconds_t)(interval * 1000000));
  }
  return 0;
}
