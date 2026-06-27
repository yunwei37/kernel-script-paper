#include <bpf/libbpf.h>
#include <net/if.h>
#include <stdint.h>
#include <stdio.h>

struct packet_event {
    uint64_t seq;
    uint32_t marker;
};

static int on_sample(void *ctx, void *data, size_t size) {
    const struct packet_event *event = data;

    (void)ctx;
    if (size >= sizeof(*event)) {
        printf("seq=%llu marker=%u\n",
               (unsigned long long)event->seq,
               event->marker);
    }
    return 0;
}

int main(void) {
    struct bpf_object *obj = bpf_object__open_file("app.bpf.o", NULL);
    struct bpf_program *prog;
    struct bpf_map *ring_map;
    struct ring_buffer *rb;
    int ifindex = if_nametoindex("lo");
    int prog_fd;

    if (!obj || bpf_object__load(obj) != 0) {
        return 1;
    }

    prog = bpf_object__find_program_by_name(obj, "emit_event");
    ring_map = bpf_object__find_map_by_name(obj, "events");
    if (!prog || !ring_map) {
        bpf_object__close(obj);
        return 1;
    }
    prog_fd = bpf_program__fd(prog);
    if (bpf_xdp_attach(ifindex, prog_fd, 0, NULL) != 0) {
        bpf_object__close(obj);
        return 1;
    }

    rb = ring_buffer__new(bpf_map__fd(ring_map), on_sample, NULL, NULL);
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
