#include <bpf/libbpf.h>
#include <errno.h>
#include <linux/perf_event.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/syscall.h>
#include <unistd.h>

static int open_perf_event(__u64 type, __u64 config) {
    struct perf_event_attr attr = {};
    attr.type = type;
    attr.size = sizeof(attr);
    attr.config = config;
    attr.sample_period = 1000000;
    attr.disabled = 1;
    return (int)syscall(SYS_perf_event_open, &attr, -1, 0, -1, PERF_FLAG_FD_CLOEXEC);
}

int main(void) {
    struct bpf_object *obj = bpf_object__open_file("app.bpf.o", NULL);
    struct bpf_program *prog;
    struct bpf_link *link;
    long long count = 0;
    int perf_fd;

    if (!obj || bpf_object__load(obj) != 0) {
        return 1;
    }

    prog = bpf_object__find_program_by_name(obj, "count_samples");
    perf_fd = open_perf_event(PERF_TYPE_HARDWARE, PERF_COUNT_HW_CACHE_MISSES);
    if (!prog || perf_fd < 0) {
        bpf_object__close(obj);
        return 1;
    }

    link = bpf_program__attach_perf_event(prog, perf_fd);
    if (libbpf_get_error(link)) {
        close(perf_fd);
        bpf_object__close(obj);
        return 1;
    }
    if (ioctl(perf_fd, PERF_EVENT_IOC_RESET, 0) != 0 ||
        ioctl(perf_fd, PERF_EVENT_IOC_ENABLE, 0) != 0) {
        bpf_link__destroy(link);
        close(perf_fd);
        bpf_object__close(obj);
        return 1;
    }
    ioctl(perf_fd, PERF_EVENT_IOC_DISABLE, 0);
    if (read(perf_fd, &count, sizeof(count)) != (ssize_t)sizeof(count)) {
        bpf_link__destroy(link);
        close(perf_fd);
        bpf_object__close(obj);
        return 1;
    }

    printf("cache=%lld\n", count);
    bpf_link__destroy(link);
    close(perf_fd);
    bpf_object__close(obj);
    return 0;
}
