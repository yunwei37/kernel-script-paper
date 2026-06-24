#include "tail_call_dispatch.skel.h"

#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <net/if.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

int main(void) {
    struct tail_call_dispatch *skel = NULL;
    int ifindex = 0;
    int rc = 1;
    __u32 prog_index = 0;
    int target_fd = -1;
    int prog_array_fd = -1;
    int entry_fd = -1;

    skel = tail_call_dispatch__open_and_load();
    if (!skel) {
        fprintf(stderr, "failed to open/load tail_call_dispatch skeleton\n");
        return 1;
    }

    prog_array_fd = bpf_map__fd(skel->maps.prog_array);
    if (prog_array_fd < 0) {
        fprintf(stderr, "failed to get prog_array fd\n");
        goto out;
    }

    target_fd = bpf_program__fd(skel->progs.drop_handler);
    if (target_fd < 0) {
        fprintf(stderr, "failed to get drop_handler fd\n");
        goto out;
    }

    if (bpf_map_update_elem(prog_array_fd, &prog_index, &target_fd, BPF_ANY) != 0) {
        fprintf(stderr, "failed to register drop_handler: %s\n", strerror(errno));
        goto out;
    }

    ifindex = if_nametoindex("lo");
    if (ifindex == 0) {
        fprintf(stderr, "failed to resolve ifindex for lo\n");
        goto out;
    }

    entry_fd = bpf_program__fd(skel->progs.packet_filter);
    if (entry_fd < 0) {
        fprintf(stderr, "failed to get packet_filter fd\n");
        goto out;
    }

    if (bpf_xdp_attach(ifindex, entry_fd, 0, NULL) != 0) {
        fprintf(stderr, "failed to attach packet_filter: %s\n", strerror(errno));
        goto out;
    }

    printf("tail_call_dispatch attached to loopback\n");
    bpf_xdp_detach(ifindex, 0, NULL);
    printf("tail_call_dispatch detached\n");
    rc = 0;

out:
    tail_call_dispatch__destroy(skel);
    return rc;
}
