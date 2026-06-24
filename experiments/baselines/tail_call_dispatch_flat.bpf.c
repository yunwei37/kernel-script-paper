#include "vmlinux.h"
#include <bpf/bpf_helpers.h>

static __always_inline int should_drop(void) {
    return 1;
}

SEC("xdp")
int packet_filter(struct xdp_md *ctx) {
    if (should_drop()) {
        return XDP_DROP;
    }
    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";
