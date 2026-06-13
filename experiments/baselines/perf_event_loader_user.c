#include "perf_event_loader.skel.h"

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
    struct perf_group_value values[4];
};

static int perf_event_open_checked(uint32_t type, uint64_t config, pid_t pid,
                                   int cpu, uint64_t period, int inherit) {
    struct perf_event_attr attr = {};
    attr.type = type;
    attr.size = sizeof(attr);
    attr.config = config;
    attr.sample_period = period;
    attr.wakeup_events = 1;
    attr.read_format = PERF_FORMAT_TOTAL_TIME_ENABLED |
                       PERF_FORMAT_TOTAL_TIME_RUNNING |
                       PERF_FORMAT_ID |
                       PERF_FORMAT_GROUP;
    attr.inherit = inherit ? 1 : 0;
    attr.disabled = 1;

    int fd = (int)syscall(SYS_perf_event_open, &attr, pid, cpu, -1,
                          PERF_FLAG_FD_CLOEXEC);
    if (fd < 0) {
        fprintf(stderr, "perf_event_open failed type=%u config=%llu: %s\n",
                type, (unsigned long long)config, strerror(errno));
    }
    return fd;
}

static int reset_enable_perf_event(int fd, const char *name) {
    if (ioctl(fd, PERF_EVENT_IOC_RESET, 0) != 0) {
        fprintf(stderr, "reset %s failed: %s\n", name, strerror(errno));
        return -1;
    }
    if (ioctl(fd, PERF_EVENT_IOC_ENABLE, 0) != 0) {
        fprintf(stderr, "enable %s failed: %s\n", name, strerror(errno));
        return -1;
    }
    return 0;
}

static long long read_scaled_count(int fd, const char *name) {
    struct perf_group_read group = {};
    ssize_t n = read(fd, &group, sizeof(group));
    if (n < 0) {
        fprintf(stderr, "read %s failed: %s\n", name, strerror(errno));
        return -1;
    }
    if (n < (ssize_t)(sizeof(uint64_t) * 3) || group.nr == 0 ||
        group.time_running == 0) {
        fprintf(stderr, "read %s returned an invalid perf group record\n", name);
        return -1;
    }
    if (group.time_enabled == group.time_running) {
        return (long long)group.values[0].value;
    }
    __uint128_t scaled = ((__uint128_t)group.values[0].value *
                          (__uint128_t)group.time_enabled) /
                         group.time_running;
    return (long long)scaled;
}

int main(void) {
    struct perf_event_loader_ebpf *skel = NULL;
    struct bpf_link *page_link = NULL;
    struct bpf_link *branch_link = NULL;
    int page_fd = -1;
    int branch_fd = -1;
    int rc = 1;

    skel = perf_event_loader_ebpf__open_and_load();
    if (!skel) {
        fprintf(stderr, "failed to open/load perf_event skeleton\n");
        goto out;
    }

    page_fd = perf_event_open_checked(PERF_TYPE_SOFTWARE,
                                      PERF_COUNT_SW_PAGE_FAULTS,
                                      0, -1, 1, 0);
    if (page_fd < 0) {
        goto out;
    }
    page_link = bpf_program__attach_perf_event(skel->progs.on_page_fault,
                                               page_fd);
    if (libbpf_get_error(page_link)) {
        fprintf(stderr, "failed to attach page-fault perf_event program\n");
        page_link = NULL;
        goto out;
    }
    if (reset_enable_perf_event(page_fd, "page_faults") != 0) {
        goto out;
    }

    branch_fd = perf_event_open_checked(PERF_TYPE_HARDWARE,
                                        PERF_COUNT_HW_BRANCH_MISSES,
                                        -1, 0, 10000000, 1);
    if (branch_fd < 0) {
        goto out;
    }
    branch_link = bpf_program__attach_perf_event(skel->progs.on_page_fault,
                                                 branch_fd);
    if (libbpf_get_error(branch_link)) {
        fprintf(stderr, "failed to attach branch-miss perf_event program\n");
        branch_link = NULL;
        goto out;
    }
    if (reset_enable_perf_event(branch_fd, "branch_misses") != 0) {
        goto out;
    }

    printf("perf_event baseline attached\n");

    volatile long long x = 0;
    for (uint32_t i = 0; i <= 10000000; i++) {
        x += 1;
    }
    if (x == -1) {
        printf("unreachable: %lld\n", x);
    }

    long long page_count = read_scaled_count(page_fd, "page_faults");
    if (page_count < 0) {
        goto out;
    }
    printf("Page-fault count: %lld\n", page_count);

    long long branch_count = read_scaled_count(branch_fd, "branch_misses");
    if (branch_count < 0) {
        goto out;
    }
    printf("Branch-miss count: %lld\n", branch_count);

    printf("perf_event baseline detached\n");
    rc = 0;

out:
    if (branch_fd >= 0) {
        ioctl(branch_fd, PERF_EVENT_IOC_DISABLE, 0);
    }
    if (page_fd >= 0) {
        ioctl(page_fd, PERF_EVENT_IOC_DISABLE, 0);
    }
    bpf_link__destroy(branch_link);
    bpf_link__destroy(page_link);
    if (branch_fd >= 0) {
        close(branch_fd);
    }
    if (page_fd >= 0) {
        close(page_fd);
    }
    perf_event_loader_ebpf__destroy(skel);
    return rc;
}
