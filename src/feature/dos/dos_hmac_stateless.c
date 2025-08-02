#include "core/or/or.h"
#include "lib/crypt_ops/crypto_hmac.h"
#include "lib/crypt_ops/crypto_rand.h"
#include "lib/log/log.h"
#include <time.h>
#include <string.h>

#define HMAC_KEY_LEN 32
#define HMAC_SIG_LEN 32
#define MIN_SOLVE_TIME 2
#define MAX_SOLVE_TIME 300
#define TOKEN_LIFETIME 7200
#define HONEYPOT_COUNT 5

static uint8_t hmac_key[HMAC_KEY_LEN];
static time_t last_key_rotation = 0;

typedef struct {
    uint32_t magic;
    time_t   issued;
    time_t   expires;
    uint32_t remaining;
    uint8_t  sig[HMAC_SIG_LEN];
} hmac_token_t;

typedef struct {
    uint8_t  id[16];
    time_t   created;
    time_t   mint;
    time_t   maxt;
    uint32_t a, b, expected;
    int      difficulty;
    char     honeypots[HONEYPOT_COUNT][32];
    uint8_t  hmac[HMAC_SIG_LEN];
} hmac_challenge_t;

static void hmac_init(void) {
    time_t now = time(NULL);
    if (!last_key_rotation || now - last_key_rotation > 86400) {
        crypto_rand(hmac_key, HMAC_KEY_LEN);
        last_key_rotation = now;
    }
}

static void hmac_sign(const void *data, size_t len, uint8_t *out) {
    crypto_hmac_sha256((char*)out, (const char*)hmac_key, HMAC_KEY_LEN,
                       data, len);
}

hmac_challenge_t* create_challenge(int diff) {
    hmac_init();
    hmac_challenge_t *c = malloc(sizeof(*c));
    memset(c,0,sizeof(*c));
    crypto_rand(c->id, 16);
    c->created = time(NULL);
    c->mint    = c->created + MIN_SOLVE_TIME;
    c->maxt    = c->created + MAX_SOLVE_TIME;
    c->difficulty = diff;
    if (diff < 2) {
        c->a = rand()%50 + 1; c->b = rand()%50 + 1;
        c->expected = c->a + c->b;
    } else {
        c->a = rand()%10 + 1; c->b = rand()%10 + 1;
        c->expected = c->a * c->b;
    }
    for(int i=0;i<HONEYPOT_COUNT;i++){
        snprintf(c->honeypots[i],32,"hp%02d_%02x",i,hmac_key[i]);
    }
    hmac_sign(c, sizeof(*c)-HMAC_SIG_LEN, c->hmac);
    return c;
}

int verify_challenge(const hmac_challenge_t *c, const char *ans,
                     time_t start, const char *hp_vals[]) {
    time_t now = time(NULL);
    if (start < c->mint || now > c->maxt) return 0;
    for(int i=0;i<HONEYPOT_COUNT;i++){
        if (hp_vals[i] && hp_vals[i][0]) return 0;
    }
    uint8_t sig[HMAC_SIG_LEN];
    hmac_sign(c, sizeof(*c)-HMAC_SIG_LEN, sig);
    if (memcmp(sig, c->hmac, HMAC_SIG_LEN)) return 0;
    if ((uint32_t)atoi(ans) != c->expected) return 0;
    return 1;
}

hmac_token_t* issue_token(void) {
    hmac_init();
    hmac_token_t *t = malloc(sizeof(*t));
    t->magic     = 0x544F5248;
    t->issued    = time(NULL);
    t->expires   = t->issued + TOKEN_LIFETIME;
    t->remaining = 500;
    hmac_sign(t, sizeof(*t)-HMAC_SIG_LEN, t->sig);
    return t;
}

int verify_token(hmac_token_t *t) {
    time_t now = time(NULL);
    if (t->magic!=0x544F5248 || now>t->expires || t->remaining==0) return 0;
    uint8_t sig[HMAC_SIG_LEN];
    hmac_sign(t, sizeof(*t)-HMAC_SIG_LEN, sig);
    if (memcmp(sig, t->sig, HMAC_SIG_LEN)) return 0;
    t->remaining--;
    hmac_sign(t, sizeof(*t)-HMAC_SIG_LEN, t->sig);
    return 1;
}
