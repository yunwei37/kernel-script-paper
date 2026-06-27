#include <bpf/libbpf.h>
#include <errno.h>
#include <linux/perf_event.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/syscall.h>
#include <unistd.h>

struct perf_group_value {
    uint64_t value;
    uint64_t id;
};

struct perf_group_read {
    uint64_t nr;
    uint64_t time_enabled;
    uint64_t time_running;
    struct perf_group_value values[2];
};

static int open_perf_event(__u64 type, __u64 config, int group_fd) {
    struct perf_event_attr attr = {};
    attr.type = type;
    attr.size = sizeof(attr);
    attr.config = config;
    attr.sample_period = 1000000;
    attr.disabled = 1;
    attr.read_format = PERF_FORMAT_GROUP | PERF_FORMAT_ID |
                       PERF_FORMAT_TOTAL_TIME_ENABLED | PERF_FORMAT_TOTAL_TIME_RUNNING;
    return (int)syscall(SYS_perf_event_open, &attr, -1, 0, group_fd, PERF_FLAG_FD_CLOEXEC);
}

int main(void) {
    struct bpf_object *obj = bpf_object__open_file("app.bpf.o", NULL);
    struct bpf_program *prog;
    struct bpf_link *cache_link;
    struct bpf_link *branch_link;
    struct perf_group_read snapshot = {};
    int cache_fd;
    int branch_fd;

    if (!obj || bpf_object__load(obj) != 0) {
        return 1;
    }

    prog = bpf_object__find_program_by_name(obj, "count_samples");
    cache_fd = open_perf_event(PERF_TYPE_HARDWARE, PERF_COUNT_HW_CACHE_MISSES, -1);
    branch_fd = open_perf_event(PERF_TYPE_HARDWARE, PERF_COUNT_HW_BRANCH_MISSES, cache_fd);
    if (!prog || cache_fd < 0 || branch_fd < 0) {
        if (cache_fd >= 0) {
            close(cache_fd);
        }
        if (branch_fd >= 0) {
            close(branch_fd);
        }
        bpf_object__close(obj);
        return 1;
    }

    cache_link = bpf_program__attach_perf_event(prog, cache_fd);
    if (libbpf_get_error(cache_link)) {
        close(branch_fd);
        close(cache_fd);
        bpf_object__close(obj);
        return 1;
    }
    branch_link = bpf_program__attach_perf_event(prog, branch_fd);
    if (libbpf_get_error(branch_link)) {
        bpf_link__destroy(cache_link);
        close(branch_fd);
        close(cache_fd);
        bpf_object__close(obj);
        return 1;
    }

    if (ioctl(cache_fd, PERF_EVENT_IOC_RESET, PERF_IOC_FLAG_GROUP) != 0 ||
        ioctl(cache_fd, PERF_EVENT_IOC_ENABLE, PERF_IOC_FLAG_GROUP) != 0) {
        bpf_link__destroy(branch_link);
        bpf_link__destroy(cache_link);
        close(branch_fd);
        close(cache_fd);
        bpf_object__close(obj);
        return 1;
    }
    ioctl(cache_fd, PERF_EVENT_IOC_DISABLE, PERF_IOC_FLAG_GROUP);
    if (read(cache_fd, &snapshot, sizeof(snapshot)) < 0) {
        bpf_link__destroy(branch_link);
        bpf_link__destroy(cache_link);
        close(branch_fd);
        close(cache_fd);
        bpf_object__close(obj);
        return 1;
    }

    printf("cache=%llu branch=%llu entries=%llu\n",
           (unsigned long long)snapshot.values[0].value,
           (unsigned long long)snapshot.values[1].value,
           (unsigned long long)snapshot.nr);
    bpf_link__destroy(branch_link);
    bpf_link__destroy(cache_link);
    close(branch_fd);
    close(cache_fd);
    bpf_object__close(obj);
    return 0;
}
