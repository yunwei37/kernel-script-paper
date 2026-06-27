#include "app.skel.h"
#include <bpf/bpf.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>

int main(void) {
    struct app_bpf *skel = app_bpf__open_and_load();
    uint32_t key = 0;
    uint64_t value = 0;

    if (!skel) {
        return 1;
    }
    if (bpf_map_lookup_elem(bpf_map__fd(skel->maps.counts), &key, &value) != 0) {
        app_bpf__destroy(skel);
        return 1;
    }

    printf("count=%" PRIu64 "\n", value);
    app_bpf__destroy(skel);
    return 0;
}
