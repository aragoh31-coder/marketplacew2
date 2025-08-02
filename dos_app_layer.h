#ifndef TOR_DOS_APP_LAYER_H
#define TOR_DOS_APP_LAYER_H

#include "core/or/or.h"
#include "core/or/connection_edge.h"

/* Function declarations for enhanced dual challenge system */
int dos_app_layer_filter_stream(edge_connection_t *edge_conn, const char *data, size_t data_len);
void dos_app_layer_init(void);
void dos_app_layer_cleanup(void);
void dos_app_layer_cleanup_expired_challenges(void);

#endif /* TOR_DOS_APP_LAYER_H */
