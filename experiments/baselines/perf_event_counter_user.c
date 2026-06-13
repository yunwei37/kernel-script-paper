#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <linux/perf_event.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

static int perf_event_open_checked(void) {
    struct perf_event_attr attr = {};
    attr.type = PERF_TYPE_SOFTWARE;
    attr.size = sizeof(attr);
    attr.config = PERF_COUNT_SW_PAGE_FAULTS;
    attr.sample_period = 1;
    attr.wakeup_events = 1;
    attr.disabled = 1;

    int fd = (int)syscall(SYS_perf_event_open, &attr, 0, -1, -1,
                          PERF_FLAG_FD_CLOEXEC);
    if (fd < 0) {
        fprintf(stderr, "perf_event_open failed: %s\n", strerror(errno));
    }
    return fd;
}

static double now_sec(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1000000000.0;
}

static int touch_fault_pages(size_t pages, int rounds) {
    long page_size = sysconf(_SC_PAGESIZE);
    if (page_size <= 0) {
        fprintf(stderr, "sysconf(_SC_PAGESIZE) failed\n");
        return -1;
    }

    size_t bytes = pages * (size_t)page_size;
    for (int round = 0; round < rounds; round++) {
        volatile unsigned char *buf = mmap(NULL, bytes, PROT_READ | PROT_WRITE,
                                           MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        if (buf == MAP_FAILED) {
            fprintf(stderr, "mmap failed: %s\n", strerror(errno));
            return -1;
        }
        for (size_t i = 0; i < pages; i++) {
            buf[i * (size_t)page_size] = (unsigned char)(i + round);
        }
        if (munmap((void *)buf, bytes) != 0) {
            fprintf(stderr, "munmap failed: %s\n", strerror(errno));
            return -1;
        }
    }
    return 0;
}

int main(int argc, char **argv) {
    if (argc != 6) {
        fprintf(stderr, "usage: %s OBJ PROG MAP PAGES ROUNDS\n", argv[0]);
        return 2;
    }

    const char *obj_path = argv[1];
    const char *prog_name = argv[2];
    const char *map_name = argv[3];
    size_t pages = strtoull(argv[4], NULL, 10);
    int rounds = atoi(argv[5]);
    if (pages == 0 || rounds <= 0) {
        fprintf(stderr, "PAGES and ROUNDS must be positive\n");
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
    if (!prog) {
        fprintf(stderr, "program not found: %s\n", prog_name);
        bpf_object__close(obj);
        return 1;
    }
    struct bpf_map *map = bpf_object__find_map_by_name(obj, map_name);
    if (!map) {
        fprintf(stderr, "map not found: %s\n", map_name);
        bpf_object__close(obj);
        return 1;
    }

    int perf_fd = perf_event_open_checked();
    if (perf_fd < 0) {
        bpf_object__close(obj);
        return 1;
    }

    struct bpf_link *link = bpf_program__attach_perf_event(prog, perf_fd);
    if (libbpf_get_error(link)) {
        fprintf(stderr, "attach perf_event failed\n");
        close(perf_fd);
        bpf_object__close(obj);
        return 1;
    }

    __u32 key = 0;
    __u64 zero = 0;
    int map_fd = bpf_map__fd(map);
    if (bpf_map_update_elem(map_fd, &key, &zero, BPF_ANY) != 0) {
        fprintf(stderr, "reset map failed: %s\n", strerror(errno));
        bpf_link__destroy(link);
        close(perf_fd);
        bpf_object__close(obj);
        return 1;
    }

    if (ioctl(perf_fd, PERF_EVENT_IOC_RESET, 0) != 0 ||
        ioctl(perf_fd, PERF_EVENT_IOC_ENABLE, 0) != 0) {
        fprintf(stderr, "enable perf_event failed: %s\n", strerror(errno));
        bpf_link__destroy(link);
        close(perf_fd);
        bpf_object__close(obj);
        return 1;
    }

    double start = now_sec();
    int workload_rc = touch_fault_pages(pages, rounds);
    double elapsed = now_sec() - start;
    ioctl(perf_fd, PERF_EVENT_IOC_DISABLE, 0);

    __u64 bpf_count = 0;
    __u64 perf_count = 0;
    if (bpf_map_lookup_elem(map_fd, &key, &bpf_count) != 0) {
        fprintf(stderr, "map lookup failed: %s\n", strerror(errno));
        workload_rc = -1;
    }
    if (read(perf_fd, &perf_count, sizeof(perf_count)) != (ssize_t)sizeof(perf_count)) {
        fprintf(stderr, "perf read failed: %s\n", strerror(errno));
        workload_rc = -1;
    }

    printf("bpf_count=%llu\n", (unsigned long long)bpf_count);
    printf("perf_count=%llu\n", (unsigned long long)perf_count);
    printf("elapsed_sec=%.9f\n", elapsed);
    printf("pages=%zu\n", pages);
    printf("rounds=%d\n", rounds);

    bpf_link__destroy(link);
    close(perf_fd);
    bpf_object__close(obj);
    return workload_rc == 0 ? 0 : 1;
}
