#include "vmlinux.h"
#include <bpf/bpf_helpers.h>

struct {
    __uint(type, BPF_MAP_TYPE_PROG_ARRAY);
    __uint(max_entries, 2);
    __type(key, __u32);
    __type(value, __u32);
} prog_array SEC(".maps");

enum ks_ip_protocol {
    KS_PROTO_ICMP = 1,
    KS_PROTO_TCP = 6,
    KS_PROTO_UDP = 17,
};

static __always_inline __u32 get_ip_protocol(struct xdp_md *ctx) {
    return KS_PROTO_TCP;
}

static __always_inline __u32 get_tcp_dest_port(struct xdp_md *ctx) {
    return 80;
}

static __always_inline __u32 get_udp_dest_port(struct xdp_md *ctx) {
    return 53;
}

SEC("xdp")
int tcp_port_classifier(struct xdp_md *ctx) {
    __u32 port = get_tcp_dest_port(ctx);

    if (port == 80 || port == 443 || port == 22) {
        return XDP_PASS;
    }
    if (port == 21 || port == 23) {
        return XDP_DROP;
    }
    return XDP_PASS;
}

SEC("xdp")
int udp_port_classifier(struct xdp_md *ctx) {
    __u32 port = get_udp_dest_port(ctx);

    if (port == 53 || port == 123) {
        return XDP_PASS;
    }
    if (port == 161 || port == 69) {
        return XDP_DROP;
    }
    return XDP_PASS;
}

SEC("xdp")
int packet_classifier(struct xdp_md *ctx) {
    __u32 protocol = get_ip_protocol(ctx);

    if (protocol == KS_PROTO_TCP) {
        bpf_tail_call(ctx, &prog_array, 1);
        return XDP_PASS; /* tail call fallback */
    }
    if (protocol == KS_PROTO_UDP) {
        bpf_tail_call(ctx, &prog_array, 0);
        return XDP_PASS; /* tail call fallback */
    }
    if (protocol == KS_PROTO_ICMP) {
        return XDP_DROP;
    }
    return XDP_ABORTED;
}

char _license[] SEC("license") = "GPL";
