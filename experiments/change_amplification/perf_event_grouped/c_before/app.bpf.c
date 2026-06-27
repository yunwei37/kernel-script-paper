#include "vmlinux.h"
#include <bpf/bpf_helpers.h>

SEC("perf_event")
int count_samples(struct bpf_perf_event_data *ctx) {
    (void)ctx;
    return 0;
}

char _license[] SEC("license") = "GPL";
