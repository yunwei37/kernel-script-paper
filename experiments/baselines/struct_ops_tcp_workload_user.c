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

int main(int argc, char **argv) {
    const char *obj_path;
    const char *map_name;
    const char *cc_name;
    size_t bytes;
    struct bpf_object *obj = NULL;
    struct bpf_map *map = NULL;
    struct bpf_link *link = NULL;
    uint64_t received = 0;
    int workload_rc;
    int destroy_rc = 0;

    if (argc != 5) {
        fprintf(stderr, "usage: %s OBJ STRUCT_OPS_MAP TCP_CC_NAME BYTES\n", argv[0]);
        return 2;
    }

    obj_path = argv[1];
    map_name = argv[2];
    cc_name = argv[3];
    bytes = (size_t)strtoull(argv[4], NULL, 10);
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

    destroy_rc = bpf_link__destroy(link);
    printf("detach_ok=%d\n", destroy_rc == 0 ? 1 : 0);
    if (destroy_rc != 0) {
        int err = destroy_rc < 0 ? -destroy_rc : errno;
        fprintf(stderr, "destroy struct_ops link failed: %s\n", strerror(err));
    }

    bpf_object__close(obj);
    return workload_rc == 0 && received == bytes && destroy_rc == 0 ? 0 : 1;
}
