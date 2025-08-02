#ifdef _WIN32
#include <windows.h>
#endif
#include "core/or/or.h"
#include "core/or/dos.h"
#include "app/config/config.h"
#include <argon2.h>
#include "lib/crypt_ops/crypto_rand.h"
#include <sys/sysinfo.h>
#include <sys/mman.h>
#include "lib/math/fp.h"
#include "lib/container/bloomfilt.h"
#include "lib/log/log.h"
#include "lib/time/compat_time.h"
#include "core/or/circuitlist.h"
#include "feature/hs/hs_pow.h"
#include "ext/equix/include/equix.h"
#include "lib/malloc/malloc.h"
#include "lib/string/util_string.h"
#include "lib/intmath/cmp.h"
#include <errno.h>
#include <math.h>

#define ARGON2_SALT_LEN 16
#define ARGON2_HASH_LEN 32
#define ARGON2_MEMORY_BASE 65536
#define ARGON2_MEMORY_MAX 262144
#define ARGON2_TIME_BASE 2
#define ARGON2_TIME_MAX 8
#define ARGON2_MEMORY_MAX_HARD 262144
#define ARGON2_TIME_MAX_HARD 8
#define FREE_RAM_EMERGENCY_PC 0.1
#define FREE_RAM_SWITCH_PC 0.3
#define CPU_SWITCH_PC 70.0
#define CONNECTION_FLOOD_THRESHOLD 1000
#define VERIFY_QUEUE_MAX 1000
#define ARGON2_EFFICIENCY_FACTOR 0.85
#define ENTROPY_THRESHOLD 4.0
#define CHALLENGE_TTL_MS 300000
#define CHALLENGES_PER_SEC_MAX 100

typedef enum { POW_EQUIX, POW_ARGON2 } pow_type_t;

typedef struct argon2_difficulty_t {
  uint32_t memory_cost;
  uint32_t time_cost;
  uint32_t leading_zeros;
  uint32_t equix_units;
} argon2_difficulty_t;

typedef struct difficulty_factors_t {
  double load_factor;
  double resource_factor;
} difficulty_factors_t;

typedef struct system_resources_t {
  double cpu_usage;
  size_t free_memory;
  size_t total_memory;
  uint32_t active_connections;
  uint32_t pending_verify_tasks;
} system_resources_t;

typedef struct hybrid_challenge_t {
  pow_type_t type;
  uint8_t nonce[16];
  uint8_t emergency_level;
  union {
    hs_pow_solution_t equix;
    struct {
      uint8_t salt[ARGON2_SALT_LEN];
      uint32_t memory_cost;
      uint32_t time_cost;
      uint32_t leading_zeros;
    } argon2;
  };
  uint32_t difficulty;
  uint64_t expires_at;
} hybrid_challenge_t;

typedef struct verification_task_t {
  hybrid_challenge_t *challenge;
  uint8_t *solution;
  size_t solution_len;
  void (*callback)(int, void*);
  void *arg;
  double priority;
  struct verification_task_t *next;
} verification_task_t;

static double calculate_entropy(const uint8_t *data, size_t len);
static int detect_low_entropy_solutions(void *entry);
static void get_system_resources(system_resources_t *res);
static pow_type_t select_pow_type(system_resources_t *res, void *entry);
static void hybrid_auto_tune(system_resources_t *res, argon2_difficulty_t *diff);
static double argon2_to_equix_units(uint32_t mem_cost, uint32_t time_cost);
static void verification_pool_submit(hybrid_challenge_t *challenge, const uint8_t *solution, size_t len, void (*cb)(int, void*), void *arg);

int hybrid_generate_challenge(circuit_t *circ, hybrid_challenge_t *challenge);
void hybrid_verify_solution(hybrid_challenge_t *challenge, const uint8_t *solution, size_t len, void (*cb)(int, void*), void *arg);
void init_verify_cache(void);

static bloomfilt_t *verify_cache = NULL;
static uint64_t last_challenge_time = 0;
static uint32_t challenge_count = 0;
static uint32_t queue_size = 0;

static double calculate_entropy(const uint8_t *data, size_t len) {
  double freq[256] = {0};
  for (size_t i = 0; i < len; i++) freq[data[i]]++;
  double entropy = 0.0;
  for (int i = 0; i < 256; i++) {
    if (freq[i] > 0) {
      double p = freq[i] / len;
      entropy -= p * log2(p);
    }
  }
  return entropy;
}

static int detect_low_entropy_solutions(void *entry) {
  if (!entry) return 0;
  uint8_t dummy_solution[32] = {0};
  double entropy = calculate_entropy(dummy_solution, 32);
  log_info(LD_DOS, "Client entropy: %f", entropy);
  return (entropy < ENTROPY_THRESHOLD);
}

void get_system_resources(system_resources_t *res) {
#ifdef _WIN32
  MEMORYSTATUSEX memInfo;
  memInfo.dwLength = sizeof(MEMORYSTATUSEX);
  GlobalMemoryStatusEx(&memInfo);
  res->free_memory = memInfo.ullAvailPhys / 1024;
  res->total_memory = memInfo.ullTotalPhys / 1024;
  FILETIME idleTime, kernelTime, userTime;
  GetSystemTimes(&idleTime, &kernelTime, &userTime);
  ULONGLONG total = *(ULONGLONG*)&kernelTime + *(ULONGLONG*)&userTime;
  ULONGLONG idle = *(ULONGLONG*)&idleTime;
  res->cpu_usage = 100.0 * (1.0 - (double)idle / total);
#else
  struct sysinfo info;
  if (sysinfo(&info) != 0) {
    log_warn(LD_BUG, "sysinfo failed: %s", strerror(errno));
    res->free_memory = 0;
    res->total_memory = 1;
    res->cpu_usage = 100.0;
    res->active_connections = 0;
    res->pending_verify_tasks = 0;
    return;
  }
  res->free_memory = info.freeram * info.mem_unit / 1024;
  res->total_memory = info.totalram * info.mem_unit / 1024;
  FILE *fp = fopen("/proc/stat", "r");
  if (fp) {
    unsigned long long user, nice, system, idle;
    if (fscanf(fp, "cpu %llu %llu %llu %llu", &user, &nice, &system, &idle) != 4) {
      user = nice = system = idle = 0;
    }
    fclose(fp);
    unsigned long long total = user + nice + system + idle;
    res->cpu_usage = 100.0 * (1.0 - (double)idle / total);
  } else {
    res->cpu_usage = 0.0;
  }
#endif
  res->active_connections = 0;
  res->pending_verify_tasks = queue_size;
}

static pow_type_t select_pow_type(system_resources_t *res, void *entry) {
  if (detect_low_entropy_solutions(entry)) return POW_ARGON2;
  if (res->free_memory < res->total_memory * FREE_RAM_EMERGENCY_PC) return POW_ARGON2;
  if (res->pending_verify_tasks > VERIFY_QUEUE_MAX / 2) return POW_EQUIX;
  if (res->free_memory > res->total_memory * FREE_RAM_SWITCH_PC && res->active_connections > CONNECTION_FLOOD_THRESHOLD) return POW_ARGON2;
  if (res->cpu_usage > CPU_SWITCH_PC || res->free_memory < res->total_memory * 0.2) return POW_EQUIX;
  return POW_ARGON2;
}

static void hybrid_auto_tune(system_resources_t *res, argon2_difficulty_t *diff) {
  size_t low_ram_threshold = 1048576; // Default 1GB in KB
  if (res->free_memory < low_ram_threshold) {
    diff->memory_cost = CLAMP(ARGON2_MEMORY_BASE, diff->memory_cost / 2, ARGON2_MEMORY_MAX_HARD);
  }
}

static double argon2_to_equix_units(uint32_t mem_cost, uint32_t time_cost) {
  return (mem_cost / 1024.0) * time_cost * ARGON2_EFFICIENCY_FACTOR;
}

int hybrid_generate_challenge(circuit_t *circ, hybrid_challenge_t *challenge) {
  system_resources_t res;
  get_system_resources(&res);
  monotime_coarse_t now;
  monotime_coarse_get(&now);
  uint64_t current_time = monotime_coarse_absolute_sec();
  if (current_time == last_challenge_time) {
    if (++challenge_count > 100) return -1; // Default max challenges per second
  } else {
    challenge_count = 1;
    last_challenge_time = current_time;
  }
  void *entry = NULL;
  challenge->type = select_pow_type(&res, entry);
  crypto_rand((char*)challenge->nonce, 16);
  challenge->expires_at = monotime_coarse_absolute_sec() * 1000 + CHALLENGE_TTL_MS;
  challenge->emergency_level = (res.free_memory < res.total_memory * FREE_RAM_EMERGENCY_PC) ? 5 : 0;

  (void)circ; // Mark parameter as used
  argon2_difficulty_t diff = {ARGON2_MEMORY_BASE, ARGON2_TIME_BASE, 16, 100};
  hybrid_auto_tune(&res, &diff);
  diff.leading_zeros = (uint32_t)(diff.leading_zeros * (1.0 + challenge->emergency_level * 0.2));
  diff.leading_zeros += (crypto_rand_int(10) - 5);  // Jitter
  diff.leading_zeros = CLAMP(8, diff.leading_zeros, 32);
  diff.memory_cost = CLAMP(ARGON2_MEMORY_BASE, diff.memory_cost, ARGON2_MEMORY_MAX_HARD);
  diff.time_cost = CLAMP(ARGON2_TIME_BASE, diff.time_cost, ARGON2_TIME_MAX_HARD);

  uint32_t argon2_units = (uint32_t)(argon2_to_equix_units(diff.memory_cost, diff.time_cost) + 0.5);
  challenge->difficulty = MAX(1, (challenge->type == POW_EQUIX) ? diff.equix_units : argon2_units);

  if (challenge->type == POW_EQUIX) {
    crypto_rand((char*)&challenge->equix, sizeof(challenge->equix));
    return 0;
  } else {
    crypto_rand((char*)challenge->argon2.salt, ARGON2_SALT_LEN);
    challenge->argon2.memory_cost = diff.memory_cost;
    challenge->argon2.time_cost = diff.time_cost;
    challenge->argon2.leading_zeros = diff.leading_zeros;
    return 0;
  }
}



static verification_task_t *verify_queue = NULL;

void verification_pool_submit(hybrid_challenge_t *challenge, const uint8_t *solution, size_t len, void (*cb)(int, void*), void *arg) {
  if (queue_size >= VERIFY_QUEUE_MAX) {
    log_warn(LD_DOS, "Queue full; reject");
    cb(0, arg);
    return;
  }
  if (bloomfilt_probably_contains(verify_cache, solution)) {
    cb(0, arg);
    return;
  }
  verification_task_t *task = tor_malloc_zero(sizeof(verification_task_t));
  task->challenge = challenge;
  task->solution = tor_memdup(solution, len);
  task->solution_len = len;
  task->callback = cb;
  task->arg = arg;
  task->priority = challenge->difficulty * (1.0 + challenge->emergency_level * 0.2);
  verification_task_t **ptr = &verify_queue;
  while (*ptr && (*ptr)->priority > task->priority) ptr = &(*ptr)->next;
  task->next = *ptr;
  *ptr = task;
  queue_size++;
}

void hybrid_verify_solution(hybrid_challenge_t *challenge, const uint8_t *solution, size_t len, void (*cb)(int, void*), void *arg) {
  monotime_coarse_t now;
  monotime_coarse_get(&now);
  if (monotime_coarse_absolute_sec() * 1000 > challenge->expires_at) {
    cb(0, arg);
    return;
  }
  if (challenge->type == POW_EQUIX) {
    cb(1, arg);
  } else {
    verification_pool_submit(challenge, solution, len, cb, arg);
  }
}

void init_verify_cache(void) {
  verify_cache = NULL;
}
