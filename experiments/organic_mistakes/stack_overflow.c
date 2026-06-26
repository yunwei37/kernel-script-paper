/* Matched mistake: a 600-byte on-stack buffer exceeds the 512-byte eBPF stack
 * limit. Base is the working xdp_count.c baseline. The buffer is indexed by a
 * runtime value so it is not optimized away; clang compiles it and the kernel
 * verifier rejects it at load. */
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, __u64);
} counts SEC(".maps");

SEC("xdp")
int count_pass(struct xdp_md *ctx) {
    __u32 key = 0;
    char large_buffer[600] = {0};
    large_buffer[ctx->ingress_ifindex % 600] = 1;

    __u64 *value = bpf_map_lookup_elem(&counts, &key);
    if (value) {
        __sync_fetch_and_add(value, (__u64)large_buffer[0]);
    }

    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";
