/* Corrected control for Heimdall Listing 5: XDP context with XDP fields. */
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>

struct {
	__uint(type, BPF_MAP_TYPE_ARRAY);
	__uint(max_entries, 2);
	__type(key, __u32);
	__type(value, __u32);
} observed SEC(".maps");

SEC("xdp")
int monitor_packets(struct xdp_md *ctx)
{
	__u32 k0 = 0, k1 = 1;
	__u32 rxq = ctx->rx_queue_index;
	__u32 ifindex = ctx->ingress_ifindex;

	bpf_map_update_elem(&observed, &k0, &rxq, BPF_ANY);
	bpf_map_update_elem(&observed, &k1, &ifindex, BPF_ANY);
	return XDP_PASS;
}

char LICENSE[] SEC("license") = "GPL";
