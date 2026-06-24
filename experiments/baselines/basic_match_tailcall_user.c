#include "basic_match_tailcall.skel.h"

#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <net/if.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

int main(void) {
    struct basic_match_tailcall *skel = NULL;
    int ifindex = 0;
    int rc = 1;
    int prog_array_fd = -1;
    int entry_fd = -1;
    int tcp_fd = -1;
    int udp_fd = -1;
    __u32 tcp_index = 1;
    __u32 udp_index = 0;

    skel = basic_match_tailcall__open_and_load();
    if (!skel) {
        fprintf(stderr, "failed to open/load basic_match_tailcall skeleton\n");
        return 1;
    }

    prog_array_fd = bpf_map__fd(skel->maps.prog_array);
    if (prog_array_fd < 0) {
        fprintf(stderr, "failed to get prog_array fd\n");
        goto out;
    }

    tcp_fd = bpf_program__fd(skel->progs.tcp_port_classifier);
    if (tcp_fd < 0) {
        fprintf(stderr, "failed to get tcp_port_classifier fd\n");
        goto out;
    }
    if (bpf_map_update_elem(prog_array_fd, &tcp_index, &tcp_fd, BPF_ANY) != 0) {
        fprintf(stderr, "failed to register tcp_port_classifier: %s\n", strerror(errno));
        goto out;
    }

    udp_fd = bpf_program__fd(skel->progs.udp_port_classifier);
    if (udp_fd < 0) {
        fprintf(stderr, "failed to get udp_port_classifier fd\n");
        goto out;
    }
    if (bpf_map_update_elem(prog_array_fd, &udp_index, &udp_fd, BPF_ANY) != 0) {
        fprintf(stderr, "failed to register udp_port_classifier: %s\n", strerror(errno));
        goto out;
    }

    ifindex = if_nametoindex("lo");
    if (ifindex == 0) {
        fprintf(stderr, "failed to resolve ifindex for lo\n");
        goto out;
    }

    entry_fd = bpf_program__fd(skel->progs.packet_classifier);
    if (entry_fd < 0) {
        fprintf(stderr, "failed to get packet_classifier fd\n");
        goto out;
    }

    if (bpf_xdp_attach(ifindex, entry_fd, 0, NULL) != 0) {
        fprintf(stderr, "failed to attach packet_classifier: %s\n", strerror(errno));
        goto out;
    }

    printf("basic_match_tailcall attached to loopback\n");
    bpf_xdp_detach(ifindex, 0, NULL);
    printf("basic_match_tailcall detached\n");
    rc = 0;

out:
    basic_match_tailcall__destroy(skel);
    return rc;
}
