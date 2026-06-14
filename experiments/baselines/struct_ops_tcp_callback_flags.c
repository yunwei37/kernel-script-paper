#include "vmlinux.h"
#include <bpf/bpf_helpers.h>

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 5);
    __type(key, __u32);
    __type(value, __u32);
} callback_flags SEC(".maps");

static __always_inline void mark_callback(__u32 key) {
    __u32 one = 1;
    bpf_map_update_elem(&callback_flags, &key, &one, BPF_ANY);
}

SEC("struct_ops/ssthresh")
__u32 ks_paper_cb_ssthresh(struct sock *sk) {
    (void)sk;
    mark_callback(0);
    return 16;
}

SEC("struct_ops/undo_cwnd")
__u32 ks_paper_cb_undo_cwnd(struct sock *sk) {
    mark_callback(1);
    return ks_paper_cb_ssthresh(sk);
}

SEC("struct_ops/cong_avoid")
void ks_paper_cb_cong_avoid(struct sock *sk, __u32 ack, __u32 acked) {
    (void)sk;
    (void)ack;
    (void)acked;
    mark_callback(2);
}

SEC("struct_ops/set_state")
void ks_paper_cb_set_state(struct sock *sk, __u8 new_state) {
    (void)sk;
    (void)new_state;
    mark_callback(3);
}

SEC("struct_ops/cwnd_event")
void ks_paper_cb_cwnd_event(struct sock *sk, enum tcp_ca_event ev) {
    (void)sk;
    (void)ev;
    mark_callback(4);
}

SEC(".struct_ops")
struct tcp_congestion_ops ks_paper_cb_cc = {
    .ssthresh = (void *)ks_paper_cb_ssthresh,
    .undo_cwnd = (void *)ks_paper_cb_undo_cwnd,
    .cong_avoid = (void *)ks_paper_cb_cong_avoid,
    .set_state = (void *)ks_paper_cb_set_state,
    .cwnd_event = (void *)ks_paper_cb_cwnd_event,
    .name = "ks_cb_cc",
};

char _license[] SEC("license") = "GPL";
