#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>

char _license[] SEC("license") = "GPL";

SEC("struct_ops/select_cpu")
s32 BPF_PROG(ks_paper_scx_select_cpu, struct task_struct *p, s32 prev_cpu, u64 wake_flags)
{
    bool direct = false;
    s32 cpu = scx_bpf_select_cpu_dfl(p, prev_cpu, wake_flags, &direct);

    if (direct) {
        scx_bpf_dsq_insert(p, SCX_DSQ_LOCAL, SCX_SLICE_DFL, 0);
    }
    return cpu;
}

SEC("struct_ops/enqueue")
void BPF_PROG(ks_paper_scx_enqueue, struct task_struct *p, u64 enq_flags)
{
    scx_bpf_dsq_insert(p, SCX_DSQ_GLOBAL, SCX_SLICE_DFL, enq_flags);
}

SEC("struct_ops/dispatch")
void BPF_PROG(ks_paper_scx_dispatch, s32 cpu, struct task_struct *prev)
{
    (void)cpu;
    (void)prev;
    /*
     * Tasks are inserted into the built-in global DSQ in enqueue().  sched_ext
     * automatically falls back to the built-in global DSQ after dispatch()
     * returns, so no explicit DSQ move is needed here.
     */
}

SEC("struct_ops/init")
s32 BPF_PROG(ks_paper_scx_init)
{
    return 0;
}

SEC("struct_ops/exit")
void BPF_PROG(ks_paper_scx_exit, struct scx_exit_info *info)
{
    (void)info;
}

SEC(".struct_ops")
struct sched_ext_ops ks_paper_scx = {
    .select_cpu = (void *)ks_paper_scx_select_cpu,
    .enqueue = (void *)ks_paper_scx_enqueue,
    .dispatch = (void *)ks_paper_scx_dispatch,
    .init = (void *)ks_paper_scx_init,
    .exit = (void *)ks_paper_scx_exit,
    .name = "ks_paper_scx",
    .timeout_ms = 1000U,
};
