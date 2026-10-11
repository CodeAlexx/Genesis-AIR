/* Test-only scheduler stall after a real partial TCP frame. This translation
 * unit is used only by genesis-channel-deadlines, never by application/runtime
 * targets. Both portions use the actual runtime with the original deadline. */
#include "air_rt.h"

static air_result_unit_net channel_deadlines_send_until(
    air_socket *socket, air_view data, uint64_t deadline_ns) {
    if (data.len < UINT64_C(262144))
        return air_net_tcp_send_until(socket, data, deadline_ns);
    air_view first = { data.ptr, UINT64_C(4096) };
    air_result_unit_net started = air_net_tcp_send_until(socket, first, deadline_ns);
    if (started.tag != AIR_TAG_OK) return started;
    air_time_sleep_ms(UINT64_C(200));
    air_view rest = { (const uint8_t *)data.ptr + 4096, data.len - 4096 };
    return air_net_tcp_send_until(socket, rest, deadline_ns);
}

/* The runtime header is already included, so only emitted calls are renamed. */
#define air_net_tcp_send_until channel_deadlines_send_until
#include GENESIS_CHANNEL_DEADLINES_C
#undef air_net_tcp_send_until
