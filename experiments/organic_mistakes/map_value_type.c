/* Matched mistake: store a string literal into a u64 map value.
 * Base is the working xdp_count.c baseline. clang emits an
 * incompatible-pointer-to-integer warning (not an error), so the bad value
 * reaches the kernel undetected. */
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
    __u64 *value = bpf_map_lookup_elem(&counts, &key);

    if (value) {
        *value = "bad";
    }

    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";
