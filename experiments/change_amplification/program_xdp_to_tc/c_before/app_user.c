#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <net/if.h>
#include <stdio.h>

int main(void) {
    struct bpf_object *obj = bpf_object__open_file("app.bpf.o", NULL);
    struct bpf_program *prog;
    int ifindex = if_nametoindex("lo");
    int prog_fd;

    if (!obj || bpf_object__load(obj) != 0) {
        return 1;
    }

    prog = bpf_object__find_program_by_name(obj, "pass_packet");
    prog_fd = bpf_program__fd(prog);
    if (bpf_xdp_attach(ifindex, prog_fd, 0, NULL) != 0) {
        bpf_object__close(obj);
        return 1;
    }

    bpf_xdp_detach(ifindex, 0, NULL);
    bpf_object__close(obj);
    return 0;
}
