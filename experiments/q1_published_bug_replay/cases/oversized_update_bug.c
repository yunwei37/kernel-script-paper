/* Heimdall Listing 6 BUG 1: write 16-byte big into 8-byte conn map value. */
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>

struct conn {
	__u32 src_ip;
	__u32 dst_ip;
};

struct big {
	__u32 a;
	__u32 b;
	__u32 c;
	__u32 d;
};

struct {
	__uint(type, BPF_MAP_TYPE_ARRAY);
	__type(key, __u32);
	__type(value, struct conn); /* value_size = 8 */
	__uint(max_entries, 1);
} data SEC(".maps");

SEC("xdp")
int map_schema_bug(struct xdp_md *ctx)
{
	__u32 key = 0;
	struct big val = { 1, 2, 3, 4 };

	/* 16B payload written into 8B slot; truncated silently. */
	bpf_map_update_elem(&data, &key, &val, BPF_ANY);
	return XDP_PASS;
}

char LICENSE[] SEC("license") = "GPL";
