#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <linux/bpf.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <time.h>
#include <unistd.h>

struct ring_event {
    uint64_t seq;
    uint32_t marker;
};

struct callback_state {
    uint64_t received;
    uint64_t bad_size;
    uint64_t bad_marker;
};

static double now_sec(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1000000000.0;
}

static int on_sample(void *ctx, void *data, size_t size) {
    struct callback_state *state = ctx;
    const struct ring_event *event = data;

    state->received++;
    if (size < sizeof(*event)) {
        state->bad_size++;
        return 0;
    }
    if (event->marker != 3203383023U) {
        state->bad_marker++;
    }
    return 0;
}

static int drain_ringbuf(struct ring_buffer *rb) {
    int total = 0;
    for (;;) {
        int rc = ring_buffer__consume(rb);
        if (rc < 0) {
            return rc;
        }
        if (rc == 0) {
            return total;
        }
        total += rc;
    }
}

static int reset_counter(int map_fd, uint32_t key) {
    uint64_t zero = 0;
    if (bpf_map_update_elem(map_fd, &key, &zero, BPF_ANY) != 0) {
        fprintf(stderr, "reset map key %u failed: %s\n", key, strerror(errno));
        return -1;
    }
    return 0;
}

static uint64_t read_counter(int map_fd, uint32_t key, int *ok) {
    uint64_t value = 0;
    if (bpf_map_lookup_elem(map_fd, &key, &value) != 0) {
        fprintf(stderr, "lookup map key %u failed: %s\n", key, strerror(errno));
        *ok = 0;
    }
    return value;
}

int main(int argc, char **argv) {
    if (argc != 7) {
        fprintf(stderr, "usage: %s OBJ PROG RINGBUF_MAP COUNT_MAP EVENTS POLL_EVERY\n", argv[0]);
        return 2;
    }

    const char *obj_path = argv[1];
    const char *prog_name = argv[2];
    const char *ringbuf_name = argv[3];
    const char *count_map_name = argv[4];
    int events = atoi(argv[5]);
    int poll_every = atoi(argv[6]);
    if (events <= 0 || poll_every <= 0) {
        fprintf(stderr, "EVENTS and POLL_EVERY must be positive\n");
        return 2;
    }

    struct rlimit rlim = {RLIM_INFINITY, RLIM_INFINITY};
    setrlimit(RLIMIT_MEMLOCK, &rlim);

    struct bpf_object *obj = bpf_object__open_file(obj_path, NULL);
    if (libbpf_get_error(obj)) {
        fprintf(stderr, "open BPF object failed: %s\n", strerror(errno));
        return 1;
    }
    if (bpf_object__load(obj) != 0) {
        fprintf(stderr, "load BPF object failed\n");
        bpf_object__close(obj);
        return 1;
    }

    struct bpf_program *prog = bpf_object__find_program_by_name(obj, prog_name);
    struct bpf_map *ring_map = bpf_object__find_map_by_name(obj, ringbuf_name);
    struct bpf_map *count_map = bpf_object__find_map_by_name(obj, count_map_name);
    if (!prog || !ring_map || !count_map) {
        fprintf(stderr, "missing program or map: prog=%p ring=%p counts=%p\n",
                (void *)prog, (void *)ring_map, (void *)count_map);
        bpf_object__close(obj);
        return 1;
    }

    int prog_fd = bpf_program__fd(prog);
    int ring_fd = bpf_map__fd(ring_map);
    int count_fd = bpf_map__fd(count_map);
    struct callback_state state = {};
    struct ring_buffer *rb = ring_buffer__new(ring_fd, on_sample, &state, NULL);
    if (libbpf_get_error(rb)) {
        fprintf(stderr, "ring_buffer__new failed\n");
        bpf_object__close(obj);
        return 1;
    }

    if (reset_counter(count_fd, 0) != 0 || reset_counter(count_fd, 1) != 0) {
        ring_buffer__free(rb);
        bpf_object__close(obj);
        return 1;
    }

    unsigned char packet[64] = {
        0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x00,
    };
    unsigned char out[128] = {};
    int bad_retval = 0;
    int run_errors = 0;

    double start = now_sec();
    for (int i = 0; i < events; i++) {
        struct bpf_test_run_opts opts = {
            .sz = sizeof(opts),
            .data_in = packet,
            .data_out = out,
            .data_size_in = sizeof(packet),
            .data_size_out = sizeof(out),
            .repeat = 1,
        };
        int rc = bpf_prog_test_run_opts(prog_fd, &opts);
        if (rc != 0) {
            run_errors++;
            continue;
        }
        if (opts.retval != XDP_PASS) {
            bad_retval++;
        }
        if ((i + 1) % poll_every == 0) {
            int drained = drain_ringbuf(rb);
            if (drained < 0) {
                fprintf(stderr, "ring buffer consume failed: %d\n", drained);
                run_errors++;
                break;
            }
        }
    }
    int drained = drain_ringbuf(rb);
    double elapsed = now_sec() - start;
    if (drained < 0) {
        fprintf(stderr, "final ring buffer consume failed: %d\n", drained);
        run_errors++;
    }

    int ok = 1;
    uint64_t submitted = read_counter(count_fd, 0, &ok);
    uint64_t dropped = read_counter(count_fd, 1, &ok);
    double rate = elapsed > 0.0 ? (double)state.received / elapsed / 1000000.0 : 0.0;

    printf("target_events=%d\n", events);
    printf("submitted=%llu\n", (unsigned long long)submitted);
    printf("dropped=%llu\n", (unsigned long long)dropped);
    printf("received=%llu\n", (unsigned long long)state.received);
    printf("bad_size=%llu\n", (unsigned long long)state.bad_size);
    printf("bad_marker=%llu\n", (unsigned long long)state.bad_marker);
    printf("bad_retval=%d\n", bad_retval);
    printf("run_errors=%d\n", run_errors);
    printf("elapsed_sec=%.9f\n", elapsed);
    printf("event_rate_mps=%.9f\n", rate);

    ring_buffer__free(rb);
    bpf_object__close(obj);
    return ok && run_errors == 0 && bad_retval == 0 && state.bad_size == 0 &&
                   state.bad_marker == 0 && dropped == 0 && submitted == state.received &&
                   submitted == (uint64_t)events
               ? 0
               : 1;
}
