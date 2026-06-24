#include "vmlinux.h"
#include <bpf/bpf_helpers.h>

struct {
    __uint(type, BPF_MAP_TYPE_PROG_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, __u32);
} prog_array SEC(".maps");

static __always_inline int validate_packet(__u32 size) {
    return size >= 64 && size <= 1500;
}

SEC("xdp")
int drop_handler(struct xdp_md *ctx) {
    return XDP_DROP;
}

SEC("xdp")
int packet_filter(struct xdp_md *ctx) {
    __u32 packet_size = 128;

    if (!validate_packet(packet_size)) {
        bpf_tail_call(ctx, &prog_array, 0);
        return XDP_PASS; /* tail call fallback */
    }

    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";
