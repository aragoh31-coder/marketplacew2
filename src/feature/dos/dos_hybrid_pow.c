#ifdef _WIN32
#include <windows.h>
#endif
#include "feature/dos/dos_pow.h"
#include <argon2.h>
#include "lib/crypt_ops/crypto_rand.h"
#include <sys/sysinfo.h>
#include <sys/mman.h>
#include "lib/math/fp.h"
#include "lib/container/bloomfilter.h"
#include "lib/log/log.h"
#include "lib/time/tor_time.h"
#include "core/or/circuitlist.h"
#include "feature/hs/hs_stats.h"
#include "lib/metrics/metrics.h"

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

typedef struct hybrid_challenge_t {
  pow_type_t type;
  uint8_t nonce[16];
  uint8_t emergency_level;
  union {
    equix_challenge_t equix;
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

typedef struct system_resources_t {
  double cpu_usage;
  size_t free_memory;
  size_t total_memory;
  uint32_t active_connections;
  uint32_t pending_verify_tasks;
} system_resources_t;

typedef struct verification_task_t {
  hybrid_challenge_t *challenge;
  uint8_t *solution;
  size_t solution_len;
  void (*callback)(int, void*);
  void *arg;
  double priority;
  struct verification_task_t *next;
} verification_task_t;

static bloom_filter_t *verify_cache = NULL;
static uint64_t last_challenge_time = 0;
static uint32_t challenge_count = 0;

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

static int detect_low_entropy_solutions(client_stats_t *stats) {
  if (stats->last_solution_len == 0) return 0;
  double entropy = calculate_entropy(stats->last_solution, stats->last_solution_len);
  log_info(LD_DOS, "Client entropy: %f", entropy);
  metrics_entry_update("pow_entropy", entropy);
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
    fscanf(fp, "cpu %llu %llu %llu %llu", &user, &nice, &system, &idle);
    fclose(fp);
    unsigned long long total = user + nice + system + idle;
    res->cpu_usage = 100.0 * (1.0 - (double)idle / total);
  } else {
    res->cpu_usage = 0.0;
  }
#endif
  res->active_connections = hs_stats_get_n_intros();
  res->pending_verify_tasks = queue_size;
}

static pow_type_t select_pow_type(system_resources_t *res, client_stats_t *stats) {
  if (detect_low_entropy_solutions(stats)) return POW_ARGON2;
  if (res->free_memory < res->total_memory * FREE_RAM_EMERGENCY_PC) return POW_ARGON2;
  if (res->pending_verify_tasks > VERIFY_QUEUE_MAX / 2) return POW_EQUIX;
  if (res->free_memory > res->total_memory * FREE_RAM_SWITCH_PC && res->active_connections > CONNECTION_FLOOD_THRESHOLD) return POW_ARGON2;
  if (res->cpu_usage > CPU_SWITCH_PC || res->free_memory < res->total_memory * 0.2) return POW_EQUIX;
  return POW_ARGON2;
}

static void hybrid_auto_tune(system_resources_t *res, argon2_difficulty_t *diff) {
  size_t low_ram_threshold = get_options()->DoSArgon2LowRamThreshold;
  if (res->free_memory < low_ram_threshold) {
    diff->memory_cost = tor_clamp(ARGON2_MEMORY_BASE, diff->memory_cost / 2, ARGON2_MEMORY_MAX_HARD);
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
  uint64_t current_time = monotime_coarse_to_msec(&now) / 1000;
  if (current_time == last_challenge_time) {
    if (++challenge_count > get_options()->DoSChallengesPerSecMax) return -1;
  } else {
    challenge_count = 1;
    last_challenge_time = current_time;
  }
  client_stats_t *stats = hs_stats_get_client_stats(circ);
  challenge->type = select_pow_type(&res, stats);
  crypto_rand(challenge->nonce, 16);
  challenge->expires_at = monotime_coarse_to_msec(&now) + CHALLENGE_TTL_MS;
  challenge->emergency_level = (res->free_memory < res->total_memory * FREE_RAM_EMERGENCY_PC) ? 5 : 0;

  difficulty_factors_t factors = hs_stats_get_difficulty_factors();
  argon2_difficulty_t diff = calculate_multi_factor_difficulty(&factors);
  hybrid_auto_tune(&res, &diff);
  diff.leading_zeros = (uint32_t)(diff.leading_zeros * (1.0 + challenge->emergency_level * 0.2));
  diff.leading_zeros += (crypto_rand_int(10) - 5);
  diff.leading_zeros = tor_clamp(8, diff.leading_zeros, 32);
  diff.memory_cost = tor_clamp(ARGON2_MEMORY_BASE, diff.memory_cost, ARGON2_MEMORY_MAX_HARD);
  diff.time_cost = tor_clamp(ARGON2_TIME_BASE, diff.time_cost, ARGON2_TIME_MAX_HARD);

  challenge->difficulty = MAX(1, (challenge->type == POW_EQUIX) ? diff.equix_units : (uint32_t)argon2_to_equix_units(diff.memory_cost, diff.time_cost));

  if (challenge->type == POW_EQUIX) {
    return equix_generate_challenge(circ, &challenge->equix);
  } else {
    crypto_rand(challenge->argon2.salt, ARGON2_SALT_LEN);
    challenge->argon2.memory_cost = diff.memory_cost;
    challenge->argon2.time_cost = diff.time_cost;
    challenge->argon2.leading_zeros = diff.leading_zeros;
    argon2_context ctx = { .version = ARGON2_VERSION_13, .t_cost = diff.time_cost, .m_cost = diff.memory_cost, .lanes = 1 };
    memcpy(ctx.salt, challenge->argon2.salt, ARGON2_SALT_LEN);
    argon2_ctx(&ctx, ARGON2_PREHASH);
    return 0;
  }
}

void *secure_malloc(size_t size) {
  void *ptr = tor_malloc(size);
  if (mlock(ptr, size) == -1) {
    log_warn(LD_CRYPTO, "mlock failed: %s", strerror(errno));
    memset(ptr, 0, size);
    tor_free(ptr);
    return NULL;
  }
  return ptr;
}

void secure_free(void *ptr, size_t size) {
  if (ptr) {
    memset(ptr, 0, size);
    munlock(ptr, size);
    tor_free(ptr);
  }
}

int argon2_verify_safe(hybrid_challenge_t *challenge, const uint8_t *solution, size_t len) {
  uint8_t *hash = secure_malloc(ARGON2_HASH_LEN);
  if (!hash) return 0;
  int ret = argon2id_hash_raw(challenge->argon2.time_cost, challenge->argon2.memory_cost, 1, solution, len, challenge->argon2.salt, ARGON2_SALT_LEN, hash, ARGON2_HASH_LEN);
  if (ret != ARGON2_OK) {
    secure_free(hash, ARGON2_HASH_LEN);
    return 0;
  }
  int result = 0;
  for (size_t i = 0; i < ARGON2_HASH_LEN; i++) {
    result |= hash[i] ^ solution[i];
  }
  secure_free(hash, ARGON2_HASH_LEN);
  return result == 0;
}

static verification_task_t *verify_queue = NULL;
static uint32_t queue_size = 0;

void verification_pool_submit(hybrid_challenge_t *challenge, const uint8_t *solution, size_t len, void (*cb)(int, void*), void *arg) {
  if (queue_size >= VERIFY_QUEUE_MAX) {
    log_warn(LD_DOS, "Queue full; reject");
    cb(0, arg);
    return;
  }
  if (bloom_filter_contains(verify_cache, solution, len)) {
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
  metrics_entry_update("pow_queue_size", queue_size);
}

void hybrid_verify_solution(hybrid_challenge_t *challenge, const uint8_t *solution, size_t len, void (*cb)(int, void*), void *arg) {
  monotime_coarse_t now;
  monotime_coarse_get(&now);
  if (monotime_coarse_to_msec(&now) > challenge->expires_at) {
    cb(0, arg);
    return;
  }
  if (challenge->type == POW_EQUIX) {
    equix_verify_solution(&challenge->equix, solution, len, cb, arg);
  } else {
    verification_pool_submit(challenge, solution, len, cb, arg);
  }
}

void init_verify_cache(void) {
  verify_cache = bloom_filter_new(10000, 0.01);
}
