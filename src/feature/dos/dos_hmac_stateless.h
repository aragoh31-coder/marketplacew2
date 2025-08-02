#ifndef DOS_HMAC_STATELESS_H
#define DOS_HMAC_STATELESS_H

#include <time.h>

#define HONEYPOT_COUNT 5

typedef struct {
    uint32_t magic;
    time_t   issued;
    time_t   expires;
    uint32_t remaining;
    uint8_t  sig[32];
} hmac_token_t;

typedef struct {
    uint8_t  id[16];
    time_t   created;
    time_t   mint, maxt;
    uint32_t a, b, expected;
    int      difficulty;
    char     honeypots[HONEYPOT_COUNT][32];
    uint8_t  hmac[32];
} hmac_challenge_t;

void       hmac_init(void);
hmac_challenge_t* create_challenge(int diff);
int        verify_challenge(const hmac_challenge_t*, const char*, time_t, const char*[]);
hmac_token_t* issue_token(void);
int        verify_token(hmac_token_t*);

#endif /* DOS_HMAC_STATELESS_H */
