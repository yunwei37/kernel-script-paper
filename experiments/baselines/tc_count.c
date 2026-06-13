#include "vmlinux.h"
#include <bpf/bpf_helpers.h>

#ifndef TC_ACT_OK
#define TC_ACT_OK 0
#endif

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, __u64);
} counts SEC(".maps");

SEC("tc/ingress")
int count_ingress(struct __sk_buff *ctx) {
    __u32 key = 0;
    __u64 *value = bpf_map_lookup_elem(&counts, &key);

    if (value) {
        __sync_fetch_and_add(value, 1);
    }

    return TC_ACT_OK;
}

char _license[] SEC("license") = "GPL";
