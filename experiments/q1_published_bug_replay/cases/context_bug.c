/* Heimdall Listing 5 (arXiv:2605.25411v1): XDP section with TC context type.
 * Observation map records the misnamed fields so a shared runner can assert
 * they equal the XDP-side rx_queue_index / ingress_ifindex values. */
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>

struct {
	__uint(type, BPF_MAP_TYPE_ARRAY);
	__uint(max_entries, 2);
	__type(key, __u32);
	__type(value, __u32);
} observed SEC(".maps");

SEC("xdp")
int monitor_packets(struct __sk_buff *skb)
{
	__u32 k0 = 0, k1 = 1;
	/* Under XDP these offsets are not protocol / queue_mapping. */
	__u32 protocol = skb->protocol;
	__u32 queue_mapping = skb->queue_mapping;

	bpf_map_update_elem(&observed, &k0, &protocol, BPF_ANY);
	bpf_map_update_elem(&observed, &k1, &queue_mapping, BPF_ANY);
	return XDP_PASS;
}

char LICENSE[] SEC("license") = "GPL";
