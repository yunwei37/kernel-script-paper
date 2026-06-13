#include "vmlinux.h"
#include <bpf/bpf_helpers.h>

SEC("struct_ops/ssthresh")
__u32 ks_paper_ssthresh(struct sock *sk) {
    (void)sk;
    return 16;
}

SEC("struct_ops/undo_cwnd")
__u32 ks_paper_undo_cwnd(struct sock *sk) {
    return ks_paper_ssthresh(sk);
}

SEC("struct_ops/cong_avoid")
void ks_paper_cong_avoid(struct sock *sk, __u32 ack, __u32 acked) {
    (void)sk;
    (void)ack;
    (void)acked;
}

SEC("struct_ops/set_state")
void ks_paper_set_state(struct sock *sk, __u8 new_state) {
    (void)sk;
    (void)new_state;
}

SEC("struct_ops/cwnd_event")
void ks_paper_cwnd_event(struct sock *sk, enum tcp_ca_event ev) {
    (void)sk;
    (void)ev;
}

SEC(".struct_ops")
struct tcp_congestion_ops ks_paper_cc = {
    .ssthresh = (void *)ks_paper_ssthresh,
    .undo_cwnd = (void *)ks_paper_undo_cwnd,
    .cong_avoid = (void *)ks_paper_cong_avoid,
    .set_state = (void *)ks_paper_set_state,
    .cwnd_event = (void *)ks_paper_cwnd_event,
    .name = "ks_paper_cc",
};

char _license[] SEC("license") = "GPL";
