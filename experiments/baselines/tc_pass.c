#include "vmlinux.h"
#include <bpf/bpf_helpers.h>

#ifndef TC_ACT_OK
#define TC_ACT_OK 0
#endif

SEC("tc/ingress")
int pass_ingress(struct __sk_buff *ctx) {
    return TC_ACT_OK;
}

char _license[] SEC("license") = "GPL";
