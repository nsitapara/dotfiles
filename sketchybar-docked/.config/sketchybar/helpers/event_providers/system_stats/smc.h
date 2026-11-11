#pragma once
#include <IOKit/IOKitLib.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

// Read one temperature key from the AppleSMC user client. No root needed;
// this is the interface Stats.app's bundled `smc` tool uses.

#define SMC_KERNEL_INDEX 2
#define SMC_CMD_READ_BYTES 5
#define SMC_CMD_READ_KEYINFO 9

typedef struct { char major, minor, build, reserved; uint16_t release; } smc_vers_t;
typedef struct { uint16_t version, length; uint32_t cpu, gpu, mem; } smc_plimit_t;
typedef struct { uint32_t data_size, data_type; uint8_t data_attributes; } smc_keyinfo_t;
typedef struct {
  uint32_t key;
  smc_vers_t vers;
  smc_plimit_t plimit;
  smc_keyinfo_t keyinfo;
  uint8_t result, status, data8;
  uint32_t data32;
  uint8_t bytes[32];
} smc_data_t;
_Static_assert(sizeof(smc_data_t) == 80, "AppleSMC expects an 80-byte struct");

struct smc {
  io_connect_t conn;
  uint32_t key;
  smc_keyinfo_t info;
  bool has_info;
};

static inline uint32_t smc_fourcc(const char* s) {
  return (uint32_t)s[0] << 24 | (uint32_t)s[1] << 16 | (uint32_t)s[2] << 8 | (uint32_t)s[3];
}

static inline bool smc_call(struct smc* smc, smc_data_t* in, smc_data_t* out) {
  size_t size = sizeof(*out);
  memset(out, 0, sizeof(*out));
  return IOConnectCallStructMethod(smc->conn, SMC_KERNEL_INDEX, in, sizeof(*in),
                                   out, &size) == KERN_SUCCESS
         && out->result == 0;
}

static inline void smc_init(struct smc* smc, const char* key) {
  memset(smc, 0, sizeof(*smc));
  smc->key = smc_fourcc(key);
  io_service_t service = IOServiceGetMatchingService(kIOMainPortDefault,
                                                     IOServiceMatching("AppleSMC"));
  if (!service) return;
  if (IOServiceOpen(service, mach_task_self(), 0, &smc->conn) != KERN_SUCCESS) smc->conn = 0;
  IOObjectRelease(service);
}

// Degrees Celsius, or -1 when the key is missing or unreadable.
static inline double smc_temperature(struct smc* smc) {
  if (!smc->conn) return -1;
  smc_data_t in, out;
  if (!smc->has_info) {
    memset(&in, 0, sizeof(in));
    in.key = smc->key;
    in.data8 = SMC_CMD_READ_KEYINFO;
    if (!smc_call(smc, &in, &out)) return -1;
    smc->info = out.keyinfo;
    smc->has_info = true;
  }
  memset(&in, 0, sizeof(in));
  in.key = smc->key;
  in.keyinfo.data_size = smc->info.data_size;
  in.data8 = SMC_CMD_READ_BYTES;
  if (!smc_call(smc, &in, &out)) return -1;

  double value = -1;
  if (smc->info.data_type == smc_fourcc("flt ") && smc->info.data_size == 4) {
    float f;
    memcpy(&f, out.bytes, sizeof(f));
    value = f;
  } else if (smc->info.data_type == smc_fourcc("sp78") && smc->info.data_size == 2) {
    value = (int8_t)out.bytes[0] + out.bytes[1] / 256.0;
  }
  return value > 10 && value < 120 ? value : -1;
}
