/* Heimdall Listing 6 BUG 2: reinterpret conn map value as unrelated stats. */
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>

struct conn {
	__u32 src_ip;
	__u32 dst_ip;
};

struct stats {
	__u64 bytes;
};

struct {
	__uint(type, BPF_MAP_TYPE_ARRAY);
	__type(key, __u32);
	__type(value, struct conn);
	__uint(max_entries, 1);
} data SEC(".maps");

/* Side channel so userspace can observe the reinterpreted u64. */
struct {
	__uint(type, BPF_MAP_TYPE_ARRAY);
	__uint(max_entries, 1);
	__type(key, __u32);
	__type(value, __u64);
} observed SEC(".maps");

SEC("xdp")
int map_schema_bug(struct xdp_md *ctx)
{
	__u32 key = 0;
	struct conn init = { 1, 2 };
	struct stats *s;
	__u64 bytes = 0;

	bpf_map_update_elem(&data, &key, &init, BPF_ANY);
	s = (struct stats *)bpf_map_lookup_elem(&data, &key);
	if (s)
		bytes = s->bytes;
	bpf_map_update_elem(&observed, &key, &bytes, BPF_ANY);
	return XDP_PASS;
}

char LICENSE[] SEC("license") = "GPL";
