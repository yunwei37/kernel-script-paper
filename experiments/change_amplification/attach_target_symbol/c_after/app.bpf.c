#include "vmlinux.h"
#include <bpf/bpf_helpers.h>

SEC("kprobe/do_group_exit")
int trace_target(struct pt_regs *ctx) {
    (void)ctx;
    return 0;
}

char _license[] SEC("license") = "GPL";
