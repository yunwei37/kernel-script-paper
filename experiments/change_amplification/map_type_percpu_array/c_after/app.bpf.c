#include "vmlinux.h"
#include <bpf/bpf_helpers.h>

struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, __u64);
} counts SEC(".maps");

SEC("perf_event")
int count_fault(struct bpf_perf_event_data *ctx) {
    __u32 key = 0;
    __u64 *value = bpf_map_lookup_elem(&counts, &key);

    if (value) {
        __sync_fetch_and_add(value, 1);
    }
    return 0;
}

char _license[] SEC("license") = "GPL";
