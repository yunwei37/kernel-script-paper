#include <arpa/inet.h>
#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <errno.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#define CALLBACK_SLOTS 5
#define CALLBACK_CONG_AVOID 2
#define CALLBACK_CWND_EVENT 4

static int set_memlock_rlimit(void) {
    struct rlimit rlim = {RLIM_INFINITY, RLIM_INFINITY};
    return setrlimit(RLIMIT_MEMLOCK, &rlim);
}

static int write_all(int fd, const char *buf, size_t len) {
    size_t off = 0;

    while (off < len) {
        ssize_t n = write(fd, buf + off, len - off);
        if (n < 0) {
            if (errno == EINTR) {
                continue;
            }
            return -1;
        }
        if (n == 0) {
            return -1;
        }
        off += (size_t)n;
    }

    return 0;
}

static int run_client(uint16_t port, const char *cc_name, size_t bytes) {
    int fd = -1;
    char selected[64] = {};
    socklen_t selected_len = sizeof(selected);
    struct sockaddr_in addr = {};
    char buf[16384];
    size_t remaining = bytes;

    fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) {
        dprintf(STDOUT_FILENO, "client_socket_ok=0\n");
        return 1;
    }
    dprintf(STDOUT_FILENO, "client_socket_ok=1\n");

    if (setsockopt(fd, IPPROTO_TCP, TCP_CONGESTION, cc_name, strlen(cc_name) + 1) != 0) {
        dprintf(STDOUT_FILENO, "cc_selected=0\n");
        dprintf(STDERR_FILENO, "setsockopt TCP_CONGESTION failed: %s\n", strerror(errno));
        close(fd);
        return 1;
    }

    if (getsockopt(fd, IPPROTO_TCP, TCP_CONGESTION, selected, &selected_len) != 0) {
        dprintf(STDOUT_FILENO, "cc_selected=0\n");
        dprintf(STDERR_FILENO, "getsockopt TCP_CONGESTION failed: %s\n", strerror(errno));
        close(fd);
        return 1;
    }

    selected[sizeof(selected) - 1] = '\0';
    dprintf(STDOUT_FILENO, "client_cc=%s\n", selected);
    dprintf(STDOUT_FILENO, "cc_selected=%d\n", strcmp(selected, cc_name) == 0 ? 1 : 0);
    if (strcmp(selected, cc_name) != 0) {
        close(fd);
        return 1;
    }

    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    addr.sin_port = htons(port);
    if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) != 0) {
        dprintf(STDERR_FILENO, "connect failed: %s\n", strerror(errno));
        close(fd);
        return 1;
    }

    memset(buf, 0x5a, sizeof(buf));
    while (remaining > 0) {
        size_t chunk = remaining < sizeof(buf) ? remaining : sizeof(buf);
        if (write_all(fd, buf, chunk) != 0) {
            dprintf(STDERR_FILENO, "write failed: %s\n", strerror(errno));
            close(fd);
            return 1;
        }
        remaining -= chunk;
    }

    shutdown(fd, SHUT_WR);
    close(fd);
    return 0;
}

static int run_tcp_workload(const char *cc_name, size_t bytes, uint64_t *received_out) {
    int listen_fd = -1;
    int conn_fd = -1;
    int one = 1;
    struct sockaddr_in addr = {};
    socklen_t addr_len = sizeof(addr);
    pid_t child;
    uint64_t received = 0;
    char buf[16384];
    int status = 0;

    listen_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (listen_fd < 0) {
        perror("socket");
        return 1;
    }

    setsockopt(listen_fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    addr.sin_port = 0;
    if (bind(listen_fd, (struct sockaddr *)&addr, sizeof(addr)) != 0) {
        perror("bind");
        close(listen_fd);
        return 1;
    }
    if (getsockname(listen_fd, (struct sockaddr *)&addr, &addr_len) != 0) {
        perror("getsockname");
        close(listen_fd);
        return 1;
    }
    if (listen(listen_fd, 1) != 0) {
        perror("listen");
        close(listen_fd);
        return 1;
    }

    child = fork();
    if (child < 0) {
        perror("fork");
        close(listen_fd);
        return 1;
    }
    if (child == 0) {
        close(listen_fd);
        _exit(run_client(ntohs(addr.sin_port), cc_name, bytes));
    }

    conn_fd = accept(listen_fd, NULL, NULL);
    close(listen_fd);
    if (conn_fd < 0) {
        perror("accept");
        waitpid(child, &status, 0);
        return 1;
    }

    for (;;) {
        ssize_t n = read(conn_fd, buf, sizeof(buf));
        if (n < 0) {
            if (errno == EINTR) {
                continue;
            }
            perror("read");
            close(conn_fd);
            waitpid(child, &status, 0);
            return 1;
        }
        if (n == 0) {
            break;
        }
        received += (uint64_t)n;
    }
    close(conn_fd);

    if (waitpid(child, &status, 0) < 0) {
        perror("waitpid");
        return 1;
    }

    *received_out = received;
    dprintf(STDOUT_FILENO, "client_ok=%d\n", WIFEXITED(status) && WEXITSTATUS(status) == 0 ? 1 : 0);
    return WIFEXITED(status) && WEXITSTATUS(status) == 0 ? 0 : 1;
}

static int reset_callback_flags(struct bpf_map *map) {
    int map_fd = bpf_map__fd(map);

    for (__u32 key = 0; key < CALLBACK_SLOTS; key++) {
        __u32 zero = 0;

        if (bpf_map_update_elem(map_fd, &key, &zero, BPF_ANY) != 0) {
            fprintf(stderr, "reset callback flag %u failed: %s\n", key, strerror(errno));
            return -1;
        }
    }

    return 0;
}

static int print_callback_flags(struct bpf_map *map, int *any_out, int *positive_slots_out, int *required_out) {
    int map_fd = bpf_map__fd(map);
    int any = 0;
    int positive_slots = 0;
    int saw_cong_avoid = 0;
    int saw_cwnd_event = 0;

    for (__u32 key = 0; key < CALLBACK_SLOTS; key++) {
        __u32 value = 0;

        if (bpf_map_lookup_elem(map_fd, &key, &value) != 0) {
            fprintf(stderr, "lookup callback flag %u failed: %s\n", key, strerror(errno));
            return -1;
        }
        printf("callback_flag_%u=%u\n", key, value);
        if (value != 0) {
            any = 1;
            positive_slots++;
        }
        if (key == CALLBACK_CONG_AVOID && value != 0) {
            saw_cong_avoid = 1;
        }
        if (key == CALLBACK_CWND_EVENT && value != 0) {
            saw_cwnd_event = 1;
        }
    }

    *any_out = any;
    *positive_slots_out = positive_slots;
    *required_out = saw_cong_avoid && saw_cwnd_event;
    printf("callback_any=%d\n", any);
    printf("callback_positive_slots=%d\n", positive_slots);
    printf("callback_required=%d\n", *required_out);
    return 0;
}

int main(int argc, char **argv) {
    const char *obj_path;
    const char *map_name;
    const char *cc_name;
    const char *callback_map_name = NULL;
    size_t bytes;
    struct bpf_object *obj = NULL;
    struct bpf_map *map = NULL;
    struct bpf_map *callback_map = NULL;
    struct bpf_link *link = NULL;
    uint64_t received = 0;
    int workload_rc;
    int destroy_rc = 0;
    int callback_any = 1;
    int callback_required = 1;
    int callback_positive_slots = 0;
    int callback_map_rc = 0;

    if (argc != 5 && argc != 6) {
        fprintf(stderr, "usage: %s OBJ STRUCT_OPS_MAP TCP_CC_NAME BYTES [CALLBACK_FLAGS_MAP]\n", argv[0]);
        return 2;
    }

    obj_path = argv[1];
    map_name = argv[2];
    cc_name = argv[3];
    bytes = (size_t)strtoull(argv[4], NULL, 10);
    if (argc == 6) {
        callback_map_name = argv[5];
        callback_any = 0;
    }
    if (bytes == 0) {
        fprintf(stderr, "BYTES must be positive\n");
        return 2;
    }

    set_memlock_rlimit();

    obj = bpf_object__open_file(obj_path, NULL);
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

    map = bpf_object__find_map_by_name(obj, map_name);
    if (!map) {
        fprintf(stderr, "struct_ops map not found: %s\n", map_name);
        bpf_object__close(obj);
        return 1;
    }

    if (callback_map_name) {
        callback_map = bpf_object__find_map_by_name(obj, callback_map_name);
        printf("callback_map_found=%d\n", callback_map ? 1 : 0);
        if (!callback_map) {
            fprintf(stderr, "callback flags map not found: %s\n", callback_map_name);
            bpf_object__close(obj);
            return 1;
        }
        if (reset_callback_flags(callback_map) != 0) {
            bpf_object__close(obj);
            return 1;
        }
    }

    link = bpf_map__attach_struct_ops(map);
    long link_err = libbpf_get_error(link);
    printf("attach_ok=%d\n", link_err ? 0 : 1);
    if (link_err) {
        fprintf(stderr, "attach struct_ops map failed: %s\n", strerror((int)-link_err));
        bpf_object__close(obj);
        return 1;
    }

    printf("cc_name=%s\n", cc_name);
    printf("bytes_requested=%zu\n", bytes);
    workload_rc = run_tcp_workload(cc_name, bytes, &received);
    printf("bytes_received=%llu\n", (unsigned long long)received);
    printf("workload_ok=%d\n", workload_rc == 0 && received == bytes ? 1 : 0);

    if (callback_map) {
        callback_map_rc = print_callback_flags(
            callback_map,
            &callback_any,
            &callback_positive_slots,
            &callback_required
        );
        if (callback_map_rc != 0) {
            workload_rc = 1;
        }
    }

    destroy_rc = bpf_link__destroy(link);
    printf("detach_ok=%d\n", destroy_rc == 0 ? 1 : 0);
    if (destroy_rc != 0) {
        int err = destroy_rc < 0 ? -destroy_rc : errno;
        fprintf(stderr, "destroy struct_ops link failed: %s\n", strerror(err));
    }

    bpf_object__close(obj);
    return workload_rc == 0 && received == bytes && destroy_rc == 0 && callback_required ? 0 : 1;
}
