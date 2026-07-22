/* Corrected control: write declared conn into conn-valued map. */
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

SEC("xdp")
int map_schema_fixed(struct xdp_md *ctx)
{
	__u32 key = 0;
	struct conn val = { 1, 2 };

	bpf_map_update_elem(&data, &key, &val, BPF_ANY);
	return XDP_PASS;
}

char LICENSE[] SEC("license") = "GPL";
