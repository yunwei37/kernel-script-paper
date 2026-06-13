#include "vmlinux.h"
#include <bpf/bpf_helpers.h>

SEC("xdp")
int pass_all(struct xdp_md *ctx) {
    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";
