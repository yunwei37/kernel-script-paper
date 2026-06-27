#include "vmlinux.h"
#include <bpf/bpf_helpers.h>

SEC("xdp")
int pass_packet(struct xdp_md *ctx) {
    (void)ctx;
    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";
