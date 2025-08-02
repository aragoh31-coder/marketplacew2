/* Hybrid Dual Challenge System for Tor - Complete Implementation */
/* Enhanced No-JS Form-Based Challenge System */

#include "core/or/connection_edge.h"
#include "feature/dos/dos_app_layer.h"
#include "core/or/or.h"
#include "lib/container/map.h"
#include "lib/container/smartlist.h"
#include "lib/string/printf.h"
#include "lib/crypt_ops/crypto_rand.h"
#include "lib/encoding/binascii.h"
#include "lib/thread/threads.h"
#include "lib/lock/compat_mutex.h"
#include "lib/container/smartlist.h"
#include "lib/container/map.h"
#include "lib/log/log.h"
#include "app/config/config.h"
#include "core/or/connection_or.h"
#include "lib/net/address.h"
#include "core/mainloop/connection.h"
#include "core/or/connection_st.h"
#include "core/or/edge_connection_st.h"
#include <time.h>
#include <string.h>

/* Challenge storage structure */
typedef struct {
  uint32_t expected_sum;
  uint32_t expected_cut;
  time_t created_at;
  uint8_t attempts;
} challenge_info_t;

/* Client statistics structure */
typedef struct {
  uint32_t requests_per_min;
  time_t last_request_time;
  uint32_t failed_challenges;
  uint8_t is_whitelisted;
  time_t whitelist_until;
  uint8_t is_blocked;
  time_t block_until;
} app_layer_client_stats_t;

/* HTTP request info structure */
typedef struct {
  char *method;
  char *path;
  char *user_agent;
  char *content_type;
  size_t content_length;
} http_request_info_t;

/* Global state with thread safety */
static strmap_t *client_stats_map = NULL;
static strmap_t *pending_challenges = NULL;
static tor_mutex_t *pending_challenges_mutex = NULL;
static tor_mutex_t *client_stats_mutex = NULL;

/* Generate cryptographically secure challenge ID */
static char *
generate_challenge_id(void)
{
  unsigned char raw[16];
  crypto_rand((char*)raw, sizeof(raw));
  char *challenge_id = tor_malloc(33);
  base16_encode(challenge_id, 33, (const char*)raw, sizeof(raw));
  return challenge_id;
}

/* Get CSS class for circle based on cut position */
static const char *
get_circle_class(int circle_num, int cut_position)
{
  return (circle_num == cut_position) ? "circle cut-circle" : "circle";
}

/* Generate enhanced no-JS dual challenge */
static char *
generate_enhanced_nojs_challenge(void)
{
  /* Generate math problem */
  uint32_t a = crypto_rand_int_range(15, 85);
  uint32_t b = crypto_rand_int_range(15, 85);
  uint32_t sum = a + b;
  
  /* Generate unique challenge ID */
  char *challenge_id = generate_challenge_id();
  
  /* Generate cut position (1-4) */
  uint32_t cut = crypto_rand_int(4) + 1;
  
  /* Store challenge state with thread safety */
  challenge_info_t *info = tor_malloc_zero(sizeof(*info));
  info->expected_sum = sum;
  info->expected_cut = cut;
  info->created_at = time(NULL);
  info->attempts = 0;
  
  tor_mutex_acquire(pending_challenges_mutex);
  strmap_set(pending_challenges, challenge_id, info);
  tor_mutex_release(pending_challenges_mutex);
  
  /* Build CSS classes for circles */
  const char *c1 = get_circle_class(1, cut);
  const char *c2 = get_circle_class(2, cut);
  const char *c3 = get_circle_class(3, cut);
  const char *c4 = get_circle_class(4, cut);
  
  /* Generate enhanced HTML - split into smaller parts to avoid compiler limits */
  char *html = tor_malloc(8192);
  
  /* Build the response in parts */
  char *part1 = tor_malloc(2048);
  char *part2 = tor_malloc(2048);
  char *part3 = tor_malloc(2048);
  char *part4 = tor_malloc(2048);
  
  tor_snprintf(part1, 2048,
    "HTTP/1.1 200 OK\r\n"
    "Content-Type: text/html; charset=UTF-8\r\n"
    "Cache-Control: no-cache, no-store, must-revalidate\r\n"
    "Content-Security-Policy: default-src 'self'; script-src 'none'\r\n"
    "\r\n"
    "<!DOCTYPE html><html><head>"
    "<meta charset=\"UTF-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
    "<title>Access Verification</title><style>"
    "*{margin:0;padding:0;box-sizing:border-box;}"
    "body{font-family:monospace;background:#1a1a1a;color:#e0e0e0;min-height:100vh;"
    "display:flex;align-items:center;justify-content:center;padding:20px;}"
    ".container{background:#2a2a2a;border:2px solid #3a3a3a;border-radius:12px;"
    "padding:40px;max-width:500px;width:100%%;text-align:center;}"
    "h1{color:#4a7c59;font-size:1.8em;margin-bottom:15px;}"
    ".step{margin:30px 0;padding:25px;background:#1e1e1e;border-radius:8px;}"
    ".math-problem{font-size:2.2em;font-weight:bold;color:#e0e0e0;margin:20px 0;}"
    ".math-input{width:140px;height:50px;font-size:1.4em;background:#1a1a1a;"
    "border:2px solid #3a3a3a;color:#e0e0e0;border-radius:6px;text-align:center;}"
    ".circles-container{display:flex;justify-content:space-around;margin:25px 0;gap:15px;}"
    ".circle{width:90px;height:90px;border-radius:50%%;background:#4a4a6a;"
    "border:3px solid #e0e0e0;display:flex;align-items:center;justify-content:center;"
    "font-size:1.6em;font-weight:bold;color:#fff;position:relative;}"
    ".cut-circle::after{content:'';position:absolute;top:-3px;left:50%%;"
    "width:5px;height:96px;background:#1a1a1a;transform:translateX(-50%%);}"
    ".submit-btn{background:#4a7c59;color:white;border:none;font-size:1.2em;"
    "padding:18px 40px;border-radius:6px;cursor:pointer;margin-top:30px;}"
    "</style></head><body>");
    
  tor_snprintf(part2, 2048,
    "<div class=\"container\">"
    "<div style=\"font-size:3em;margin-bottom:20px;\">🧅</div>"
    "<h1>Access Verification</h1>"
    "<p>Complete both verification steps to access this service.</p>"
    "<form method=\"POST\" action=\"/verify\">"
    "<input type=\"hidden\" name=\"challenge_id\" value=\"%s\">", challenge_id);
    
  tor_snprintf(part3, 2048,
    "<div class=\"step\"><h2>📊 Step 1: Solve the Math</h2>"
    "<div class=\"math-problem\">%u + %u = ?</div>"
    "<input type=\"text\" name=\"answer\" class=\"math-input\" required autofocus></div>", a, b);
    
  tor_snprintf(part4, 2048,
    "<div class=\"step\"><h2>🎯 Step 2: Find the Cut Circle</h2>"
    "<div class=\"circles-container\">"
    "<label><input type=\"radio\" name=\"captcha\" value=\"1\" required style=\"display:none;\">"
    "<div class=\"%s\">1</div></label>"
    "<label><input type=\"radio\" name=\"captcha\" value=\"2\" style=\"display:none;\">"
    "<div class=\"%s\">2</div></label>"
    "<label><input type=\"radio\" name=\"captcha\" value=\"3\" style=\"display:none;\">"
    "<div class=\"%s\">3</div></label>"
    "<label><input type=\"radio\" name=\"captcha\" value=\"4\" style=\"display:none;\">"
    "<div class=\"%s\">4</div></label>"
    "</div></div>"
    "<button type=\"submit\" class=\"submit-btn\">Verify Access</button>"
    "</form></div></body></html>", c1, c2, c3, c4);
  
  /* Combine all parts */
  tor_snprintf(html, 8192, "%s%s%s%s", part1, part2, part3, part4);
  
  tor_free(part1);
  tor_free(part2);
  tor_free(part3);
  tor_free(part4);
  
  int written = strlen(html);
  
  if (written >= 4096) {
    log_warn(LD_DOS, "Challenge HTML truncated");
  }
  
  tor_free(challenge_id);
  return html;
}

/* Parse HTTP request */
static http_request_info_t *
parse_http_request(const char *data, size_t data_len)
{
  if (!data || data_len == 0) return NULL;
  
  http_request_info_t *request = tor_malloc_zero(sizeof(*request));
  
  /* Simple HTTP parsing - extract method and path */
  const char *space1 = strchr(data, ' ');
  if (space1) {
    request->method = tor_strndup(data, space1 - data);
    const char *space2 = strchr(space1 + 1, ' ');
    if (space2) {
      request->path = tor_strndup(space1 + 1, space2 - space1 - 1);
    }
  }
  
  return request;
}

/* Check if this is a verify request */
static int
is_verify_request(const http_request_info_t *request)
{
  return (request && request->method && request->path &&
          strcmp(request->method, "POST") == 0 &&
          strcmp(request->path, "/verify") == 0);
}

/* Extract form field from POST data */
static char *
extract_form_field(const char *data, const char *field_name)
{
  if (!data || !field_name) return NULL;
  
  char pattern[128];
  tor_snprintf(pattern, sizeof(pattern), "%s=", field_name);
  
  const char *start = strstr(data, pattern);
  if (start) {
    start += strlen(pattern);
    const char *end = strchr(start, '&');
    if (!end) end = strchr(start, '\r');
    if (!end) end = strchr(start, '\n');
    if (!end) end = start + strlen(start);
    
    if (end > start) {
      return tor_strndup(start, end - start);
    }
  }
  return NULL;
}

/* Get client statistics */
static app_layer_client_stats_t *
get_client_stats(const char *client_id)
{
  if (!client_id) return NULL;
  
  tor_mutex_acquire(client_stats_mutex);
  
  app_layer_client_stats_t *stats = strmap_get(client_stats_map, client_id);
  if (!stats) {
    stats = tor_malloc_zero(sizeof(*stats));
    strmap_set(client_stats_map, client_id, stats);
  }
  
  tor_mutex_release(client_stats_mutex);
  return stats;
}

/* Check rate limits */
static int
check_rate_limit(app_layer_client_stats_t *stats)
{
  time_t now = time(NULL);
  
  /* Simple rate limiting - trigger challenge after too many requests */
  if (now != stats->last_request_time) {
    stats->requests_per_min = 1;
    stats->last_request_time = now;
  } else {
    stats->requests_per_min++;
  }
  
  /* Trigger challenge if over limit (default 90 requests per minute) */
  return (stats->requests_per_min > 90);
}


/* Validate dual challenge */
static int
validate_dual_challenge(const char *challenge_id, const char *math_str, const char *captcha_str)
{
  if (!challenge_id || !math_str || !captcha_str) return 0;
  
  tor_mutex_acquire(pending_challenges_mutex);
  
  challenge_info_t *info = strmap_get(pending_challenges, challenge_id);
  if (!info) {
    tor_mutex_release(pending_challenges_mutex);
    log_info(LD_DOS, "Challenge not found: %.8s...", challenge_id);
    return 0;
  }
  
  /* Check expiration (default 120 seconds) */
  time_t now = time(NULL);
  int ttl = 120; /* Default TTL */
  if (now > info->created_at + ttl) {
    strmap_remove(pending_challenges, challenge_id);
    tor_free(info);
    tor_mutex_release(pending_challenges_mutex);
    log_info(LD_DOS, "Challenge expired: %.8s...", challenge_id);
    return 0;
  }
  
  /* Increment attempts */
  info->attempts++;
  
  /* Validate both answers */
  int math_answer = atoi(math_str);
  int captcha_choice = atoi(captcha_str);
  
  int math_correct = (math_answer == (int)info->expected_sum);
  int captcha_correct = (captcha_choice == (int)info->expected_cut);
  int both_correct = math_correct && captcha_correct;
  
  log_info(LD_DOS, "Challenge validation (%.8s...): math=%s captcha=%s attempt=%d", 
           challenge_id,
           math_correct ? "✓" : "✗",
           captcha_correct ? "✓" : "✗",
           info->attempts);
  
  /* Clean up challenge on success or max attempts */
  if (both_correct || info->attempts >= 3) {
    strmap_remove(pending_challenges, challenge_id);
    tor_free(info);
  }
  
  tor_mutex_release(pending_challenges_mutex);
  return both_correct;
}

/* Main integration function */
int
dos_app_layer_filter_stream(edge_connection_t *edge_conn,
                           const char *data, size_t data_len)
{
  time_t now = time(NULL);
  char client_id[INET6_ADDRSTRLEN];
  
  /* Get client IP address */
  if (!tor_addr_to_str(client_id, &edge_conn->base_.addr, sizeof(client_id), 1)) {
    return -1;
  }
  
  app_layer_client_stats_t *stats = get_client_stats(client_id);
  if (!stats) return -1;
  
  /* Check if client is currently blocked */
  if (stats->is_blocked && now < stats->block_until) {
    return -1;
  }
  stats->is_blocked = 0;
  
  /* Parse HTTP request */
  http_request_info_t *request = parse_http_request(data, data_len);
  
  /* 1) Allow whitelisted clients */
  if (stats->is_whitelisted && now < stats->whitelist_until) {
    goto cleanup_allow;
  }
  stats->is_whitelisted = 0;
  
  /* 2) Handle POST /verify submissions */
  if (is_verify_request(request)) {
    char *challenge_id = extract_form_field(data, "challenge_id");
    char *math_answer = extract_form_field(data, "answer");
    char *captcha_answer = extract_form_field(data, "captcha");
    
    if (validate_dual_challenge(challenge_id, math_answer, captcha_answer)) {
      /* Success - whitelist client */
      stats->is_whitelisted = 1;
      stats->whitelist_until = now + 3600; /* 1 hour whitelist */
      stats->failed_challenges = 0;
      
      log_info(LD_DOS, "Dual challenge SUCCESS for %s", client_id);
      
      /* Send success redirect */
      const char *redirect = 
        "HTTP/1.1 302 Found\r\n"
        "Location: /\r\n"
        "Set-Cookie: tor_verified=1; Max-Age=3600; HttpOnly; Secure; SameSite=Strict\r\n"
        "Cache-Control: no-cache\r\n"
        "\r\n";
      
      connection_buf_add(redirect, strlen(redirect), TO_CONN(edge_conn));
      
      tor_free(challenge_id);
      tor_free(math_answer);
      tor_free(captcha_answer);
      goto cleanup_handled;
    } else {
      /* Failed challenge */
      stats->failed_challenges++;
      log_info(LD_DOS, "Dual challenge FAILED for %s (attempt %d)", 
               client_id, stats->failed_challenges);
    }
    
    tor_free(challenge_id);
    tor_free(math_answer);
    tor_free(captcha_answer);
  }
  
  /* 3) Check rate limits and other protections */
  if (check_rate_limit(stats)) {
    goto send_challenge;
  }
  
  goto cleanup_allow;

send_challenge:
  /* 4) Send dual challenge if under failure limit */
  if (stats->failed_challenges < 3) {
    char *challenge_html = generate_enhanced_nojs_challenge();
    connection_buf_add(challenge_html, strlen(challenge_html), TO_CONN(edge_conn));
    tor_free(challenge_html);
    
    goto cleanup_handled;
  }
  
  /* 5) Block if too many failures */
  if (stats->failed_challenges >= 3) {
    stats->is_blocked = 1;
    stats->block_until = now + 600; /* 10 minute block */
    log_info(LD_DOS, "Blocking %s after %d failed challenges", 
             client_id, stats->failed_challenges);
  }
  
  goto cleanup_block;

cleanup_allow:
  if (request) {
    tor_free(request->method);
    tor_free(request->path);
    tor_free(request->user_agent);
    tor_free(request->content_type);
    tor_free(request);
  }
  return 0;  /* Allow request */

cleanup_handled:
  if (request) {
    tor_free(request->method);
    tor_free(request->path);
    tor_free(request->user_agent);
    tor_free(request->content_type);
    tor_free(request);
  }
  return 1;  /* Request handled (challenge sent or redirect) */

cleanup_block:
  if (request) {
    tor_free(request->method);
    tor_free(request->path);
    tor_free(request->user_agent);
    tor_free(request->content_type);
    tor_free(request);
  }
  return -1; /* Block request */
}

/* Periodic cleanup */
void
dos_app_layer_cleanup_expired_challenges(void)
{
  if (!pending_challenges) return;
  
  time_t now = time(NULL);
  int ttl = 120; /* Default TTL */
  int cleaned = 0;
  
  tor_mutex_acquire(pending_challenges_mutex);
  
  /* Create list of expired keys */
  smartlist_t *expired_keys = smartlist_new();
  
  STRMAP_FOREACH(pending_challenges, key, challenge_info_t *, info) {
    if (now > info->created_at + ttl) {
      smartlist_add(expired_keys, tor_strdup(key));
    }
  } STRMAP_FOREACH_END;
  
  /* Remove expired challenges */
  SMARTLIST_FOREACH_BEGIN(expired_keys, char *, expired_key) {
    challenge_info_t *expired_info = strmap_remove(pending_challenges, expired_key);
    if (expired_info) {
      tor_free(expired_info);
      cleaned++;
    }
    tor_free(expired_key);
  } SMARTLIST_FOREACH_END(expired_key);
  
  smartlist_free(expired_keys);
  tor_mutex_release(pending_challenges_mutex);
  
  if (cleaned > 0) {
    log_info(LD_DOS, "Cleaned up %d expired challenges", cleaned);
  }
}

/* Initialization */
void
dos_app_layer_init(void)
{
  client_stats_map = strmap_new();
  pending_challenges = strmap_new();
  pending_challenges_mutex = tor_mutex_new_nonrecursive();
  client_stats_mutex = tor_mutex_new_nonrecursive();
  
  log_info(LD_DOS, "Enhanced dual challenge system initialized");
}

/* Cleanup */
void
dos_app_layer_cleanup(void)
{
  if (client_stats_map) {
    STRMAP_FOREACH(client_stats_map, key, app_layer_client_stats_t *, stats) {
      tor_free(stats);
    } STRMAP_FOREACH_END;
    strmap_free(client_stats_map, NULL);
    client_stats_map = NULL;
  }
  
  if (pending_challenges) {
    STRMAP_FOREACH(pending_challenges, key, challenge_info_t *, info) {
      tor_free(info);
    } STRMAP_FOREACH_END;
    strmap_free(pending_challenges, NULL);
    pending_challenges = NULL;
  }
  
  if (pending_challenges_mutex) {
    tor_mutex_free(pending_challenges_mutex);
    pending_challenges_mutex = NULL;
  }
  
  if (client_stats_mutex) {
    tor_mutex_free(client_stats_mutex);
    client_stats_mutex = NULL;
  }
  
  log_info(LD_DOS, "Enhanced dual challenge system cleaned up");
}
