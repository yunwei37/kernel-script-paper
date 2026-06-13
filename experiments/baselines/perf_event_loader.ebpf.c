#include "vmlinux.h"
#include <bpf/bpf_helpers.h>

SEC("perf_event")
int on_page_fault(struct bpf_perf_event_data *ctx) {
    return 0;
}

char _license[] SEC("license") = "GPL";
