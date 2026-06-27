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

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 2);
    __type(key, __u32);
    __type(value, __u64);
} counts SEC(".maps");

SEC("xdp")
int count_packets(struct xdp_md *ctx) {
    __u32 submitted_key = 0;
    __u32 dropped_key = 1;
    __u64 *submitted;
    struct packet_event *event;

    (void)ctx;
    submitted = bpf_map_lookup_elem(&counts, &submitted_key);
    event = bpf_ringbuf_reserve(&events, sizeof(*event), 0);
    if (!event) {
        __u64 *dropped = bpf_map_lookup_elem(&counts, &dropped_key);
        if (dropped) {
            __sync_fetch_and_add(dropped, 1);
        }
        return XDP_PASS;
    }

    event->seq = submitted ? *submitted : 0;
    event->marker = 3203383023U;
    bpf_ringbuf_submit(event, 0);
    if (submitted) {
        __sync_fetch_and_add(submitted, 1);
    }
    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";
