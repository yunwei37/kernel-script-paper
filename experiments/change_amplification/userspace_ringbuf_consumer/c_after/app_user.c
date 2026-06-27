#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <net/if.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

struct packet_event {
    uint64_t seq;
    uint32_t marker;
};

struct callback_state {
    uint64_t received;
};

static int on_sample(void *ctx, void *data, size_t size) {
    struct callback_state *state = ctx;
    const struct packet_event *event = data;

    if (size >= sizeof(*event)) {
        printf("seq=%llu marker=%u\n",
               (unsigned long long)event->seq,
               event->marker);
    }
    state->received++;
    return 0;
}

int main(void) {
    struct bpf_object *obj = bpf_object__open_file("app.bpf.o", NULL);
    struct bpf_program *prog;
    struct bpf_map *count_map;
    struct bpf_map *ring_map;
    struct ring_buffer *rb;
    struct callback_state state = {};
    int ifindex = if_nametoindex("lo");
    int prog_fd;
    uint32_t key = 0;
    uint64_t submitted = 0;

    if (!obj || bpf_object__load(obj) != 0) {
        return 1;
    }

    prog = bpf_object__find_program_by_name(obj, "count_packets");
    count_map = bpf_object__find_map_by_name(obj, "counts");
    ring_map = bpf_object__find_map_by_name(obj, "events");
    if (!prog || !count_map || !ring_map) {
        bpf_object__close(obj);
        return 1;
    }
    prog_fd = bpf_program__fd(prog);

    if (bpf_xdp_attach(ifindex, prog_fd, 0, NULL) != 0) {
        bpf_object__close(obj);
        return 1;
    }

    if (bpf_map_lookup_elem(bpf_map__fd(count_map), &key, &submitted) != 0) {
        fprintf(stderr, "lookup failed: %s\n", strerror(errno));
        bpf_xdp_detach(ifindex, 0, NULL);
        bpf_object__close(obj);
        return 1;
    }

    printf("submitted=%llu\n", (unsigned long long)submitted);
    rb = ring_buffer__new(bpf_map__fd(ring_map), on_sample, &state, NULL);
    if (libbpf_get_error(rb)) {
        bpf_xdp_detach(ifindex, 0, NULL);
        bpf_object__close(obj);
        return 1;
    }

    ring_buffer__consume(rb);
    ring_buffer__free(rb);
    bpf_xdp_detach(ifindex, 0, NULL);
    bpf_object__close(obj);
    return 0;
}
