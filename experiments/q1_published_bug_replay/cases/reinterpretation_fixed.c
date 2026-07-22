/* Corrected control: lookup declared conn type only. */
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>

struct conn {
	__u32 src_ip;
	__u32 dst_ip;
};

struct {
	__uint(type, BPF_MAP_TYPE_ARRAY);
	__type(key, __u32);
	__type(value, struct conn);
	__uint(max_entries, 1);
} data SEC(".maps");

struct {
	__uint(type, BPF_MAP_TYPE_ARRAY);
	__uint(max_entries, 2);
	__type(key, __u32);
	__type(value, __u32);
} observed SEC(".maps");

SEC("xdp")
int map_schema_fixed(struct xdp_md *ctx)
{
	__u32 key = 0, k0 = 0, k1 = 1;
	struct conn init = { 1, 2 };
	struct conn *c;

	bpf_map_update_elem(&data, &key, &init, BPF_ANY);
	c = bpf_map_lookup_elem(&data, &key);
	if (c) {
		bpf_map_update_elem(&observed, &k0, &c->src_ip, BPF_ANY);
		bpf_map_update_elem(&observed, &k1, &c->dst_ip, BPF_ANY);
	}
	return XDP_PASS;
}

char LICENSE[] SEC("license") = "GPL";
