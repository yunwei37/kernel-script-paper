#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <unistd.h>

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "usage: %s OBJ STRUCT_OPS_MAP\n", argv[0]);
        return 2;
    }

    const char *obj_path = argv[1];
    const char *map_name = argv[2];

    struct rlimit rlim = {RLIM_INFINITY, RLIM_INFINITY};
    setrlimit(RLIMIT_MEMLOCK, &rlim);

    struct bpf_object *obj = bpf_object__open_file(obj_path, NULL);
    if (libbpf_get_error(obj)) {
        fprintf(stderr, "open BPF object failed: %s\n", strerror(errno));
        return 1;
    }

    int load_rc = bpf_object__load(obj);
    printf("load_ok=%d\n", load_rc == 0 ? 1 : 0);
    if (load_rc != 0) {
        fprintf(stderr, "load BPF object failed\n");
        bpf_object__close(obj);
        return 1;
    }

    struct bpf_map *map = bpf_object__find_map_by_name(obj, map_name);
    if (!map) {
        fprintf(stderr, "struct_ops map not found: %s\n", map_name);
        bpf_object__close(obj);
        return 1;
    }

    struct bpf_link *link = bpf_map__attach_struct_ops(map);
    long link_err = libbpf_get_error(link);
    printf("attach_ok=%d\n", link_err ? 0 : 1);
    if (link_err) {
        fprintf(stderr, "attach struct_ops map failed: %s\n", strerror((int)-link_err));
        bpf_object__close(obj);
        return 1;
    }

    int destroy_rc = bpf_link__destroy(link);
    printf("detach_ok=%d\n", destroy_rc == 0 ? 1 : 0);
    if (destroy_rc != 0) {
        int err = destroy_rc < 0 ? -destroy_rc : errno;
        fprintf(stderr, "destroy struct_ops link failed: %s\n", strerror(err));
        bpf_object__close(obj);
        return 1;
    }

    bpf_object__close(obj);
    return 0;
}
