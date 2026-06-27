#include "vmlinux.h"
#include <bpf/bpf_helpers.h>

struct packet_event {
    __u64 seq;
    __u32 marker;
};

struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 4096);
} events SEC(".maps");

SEC("xdp")
int emit_event(struct xdp_md *ctx) {
    struct packet_event *event;

    (void)ctx;
    event = bpf_ringbuf_reserve(&events, sizeof(*event), 0);
    if (!event) {
        return XDP_PASS;
    }
    event->seq = 1;
    event->marker = 3203383023U;
    bpf_ringbuf_submit(event, 0);
    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";
