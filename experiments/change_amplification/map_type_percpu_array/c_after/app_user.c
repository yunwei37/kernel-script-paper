#include "app.skel.h"
#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>

int main(void) {
    struct app_bpf *skel = app_bpf__open_and_load();
    int nr_cpus;
    uint32_t key = 0;
    uint64_t total = 0;

    if (!skel) {
        return 1;
    }
    nr_cpus = libbpf_num_possible_cpus();
    if (nr_cpus < 0) {
        app_bpf__destroy(skel);
        return 1;
    }
    uint64_t values[nr_cpus];
    if (bpf_map_lookup_elem(bpf_map__fd(skel->maps.counts), &key, values) != 0) {
        app_bpf__destroy(skel);
        return 1;
    }
    for (int cpu = 0; cpu < nr_cpus; cpu++) {
        total += values[cpu];
    }

    printf("count=%" PRIu64 "\n", total);
    app_bpf__destroy(skel);
    return 0;
}
