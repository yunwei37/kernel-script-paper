#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <net/if.h>
#include <stdio.h>

int main(void) {
    struct bpf_object *obj = bpf_object__open_file("app.bpf.o", NULL);
    struct bpf_program *prog;
    struct bpf_tc_hook hook = {};
    struct bpf_tc_opts opts = {};
    int ifindex = if_nametoindex("lo");

    if (!obj || bpf_object__load(obj) != 0) {
        return 1;
    }

    prog = bpf_object__find_program_by_name(obj, "pass_packet");
    hook.sz = sizeof(hook);
    hook.ifindex = ifindex;
    hook.attach_point = BPF_TC_INGRESS;
    opts.sz = sizeof(opts);
    opts.prog_fd = bpf_program__fd(prog);

    if (bpf_tc_hook_create(&hook) != 0) {
        bpf_object__close(obj);
        return 1;
    }
    if (bpf_tc_attach(&hook, &opts) != 0) {
        bpf_tc_hook_destroy(&hook);
        bpf_object__close(obj);
        return 1;
    }

    bpf_tc_detach(&hook, &opts);
    bpf_tc_hook_destroy(&hook);
    bpf_object__close(obj);
    return 0;
}
