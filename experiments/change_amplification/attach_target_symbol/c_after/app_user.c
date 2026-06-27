#include <bpf/libbpf.h>
#include <stdbool.h>

int main(void) {
    struct bpf_object *obj = bpf_object__open_file("app.bpf.o", NULL);
    struct bpf_program *prog;
    struct bpf_link *link;

    if (!obj || bpf_object__load(obj) != 0) {
        return 1;
    }

    prog = bpf_object__find_program_by_name(obj, "trace_target");
    link = bpf_program__attach_kprobe(prog, false, "do_group_exit");
    if (libbpf_get_error(link)) {
        bpf_object__close(obj);
        return 1;
    }

    bpf_link__destroy(link);
    bpf_object__close(obj);
    return 0;
}
