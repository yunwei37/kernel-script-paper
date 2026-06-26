/* Matched mistake: look up a map that was never declared (typo for `counts`).
 * Base is the working xdp_count.c baseline. */
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
    __u64 *value = bpf_map_lookup_elem(&missing_counts, &key);

    if (value) {
        __sync_fetch_and_add(value, 1);
    }

    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";
