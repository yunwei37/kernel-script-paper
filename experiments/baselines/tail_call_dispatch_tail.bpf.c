#include "vmlinux.h"
#include <bpf/bpf_helpers.h>

struct {
    __uint(type, BPF_MAP_TYPE_PROG_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, __u32);
} prog_array SEC(".maps");

static __always_inline int should_drop(void) {
    return 1;
}

SEC("xdp")
int drop_handler(struct xdp_md *ctx) {
    return XDP_DROP;
}

SEC("xdp")
int packet_filter(struct xdp_md *ctx) {
    if (should_drop()) {
        bpf_tail_call(ctx, &prog_array, 0);
        return XDP_PASS; /* tail call fallback */
    }
    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";
