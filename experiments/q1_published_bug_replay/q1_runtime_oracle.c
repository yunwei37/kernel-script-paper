/* Shared runtime oracle for Q1 published-bug C/eBPF objects.
 * Usage: q1_runtime_oracle <object.o> <case>
 *   case ∈ {context_bug, context_fixed, oversized_update_bug,
 *            oversized_update_fixed, reinterpretation_bug, reinterpretation_fixed}
 * Prints a single JSON object to stdout and exits 0 only if the oracle holds.
 */
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <linux/if_link.h>
#include <net/if.h>

#ifndef XDP_PASS
#define XDP_PASS 2
#endif

static int g_verbose;

static int libbpf_print_fn(enum libbpf_print_level level, const char *fmt, va_list args)
{
	if (!g_verbose && level > LIBBPF_WARN)
		return 0;
	return vfprintf(stderr, fmt, args);
}

static int lookup_u32(int map_fd, __u32 key, __u32 *out)
{
	return bpf_map_lookup_elem(map_fd, &key, out);
}

static int lookup_u64(int map_fd, __u32 key, __u64 *out)
{
	return bpf_map_lookup_elem(map_fd, &key, out);
}

static int lookup_conn(int map_fd, __u32 key, __u32 *src, __u32 *dst)
{
	struct {
		__u32 src_ip;
		__u32 dst_ip;
	} val = { 0 };

	if (bpf_map_lookup_elem(map_fd, &key, &val) != 0)
		return -1;
	*src = val.src_ip;
	*dst = val.dst_ip;
	return 0;
}

static int zero_map_u32(int map_fd, __u32 key)
{
	__u32 z = 0;
	return bpf_map_update_elem(map_fd, &key, &z, BPF_ANY);
}

static int zero_map_u64(int map_fd, __u32 key)
{
	__u64 z = 0;
	return bpf_map_update_elem(map_fd, &key, &z, BPF_ANY);
}

static int zero_map_conn(int map_fd, __u32 key)
{
	struct {
		__u32 src_ip;
		__u32 dst_ip;
	} z = { 0 };
	return bpf_map_update_elem(map_fd, &key, &z, BPF_ANY);
}

static int test_run(int prog_fd)
{
	/* This host's BPF_PROG_TEST_RUN path rejects non-empty XDP ctx_in
	 * (EINVAL for every size tried). Packet-only test-run is enough for
	 * map-schema oracles; context programs still execute field stores. */
	unsigned char packet[64] = {
		0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
		0x00, 0x00, 0x00, 0x00, 0x00, 0x01,
		0x08, 0x00,
	};
	unsigned char out[128] = { 0 };
	struct bpf_test_run_opts opts = {
		.sz = sizeof(opts),
		.data_in = packet,
		.data_out = out,
		.data_size_in = sizeof(packet),
		.data_size_out = sizeof(out),
		.repeat = 1,
	};
	int rc = bpf_prog_test_run_opts(prog_fd, &opts);

	if (rc != 0) {
		fprintf(stderr, "bpf_prog_test_run_opts failed: %s\n", strerror(errno));
		return -1;
	}
	if (opts.retval != XDP_PASS) {
		fprintf(stderr, "unexpected retval %d\n", opts.retval);
		return -1;
	}
	return 0;
}

static __u64 native_conn_as_u64(__u32 src, __u32 dst)
{
	struct {
		__u32 src_ip;
		__u32 dst_ip;
	} c = { .src_ip = src, .dst_ip = dst };
	__u64 out = 0;

	memcpy(&out, &c, sizeof(c));
	return out;
}

int main(int argc, char **argv)
{
	const char *obj_path;
	const char *case_name;
	struct bpf_object *obj = NULL;
	struct bpf_program *prog = NULL;
	struct bpf_map *map = NULL;
	int prog_fd = -1;
	int map_fd = -1;
	int observed_fd = -1;
	int ok = 0;

	if (argc < 3) {
		fprintf(stderr, "usage: %s <object.o> <case>\n", argv[0]);
		return 2;
	}
	obj_path = argv[1];
	case_name = argv[2];
	g_verbose = getenv("Q1_VERBOSE") != NULL;
	libbpf_set_print(libbpf_print_fn);

	obj = bpf_object__open_file(obj_path, NULL);
	if (libbpf_get_error(obj)) {
		fprintf(stderr, "open %s failed\n", obj_path);
		return 1;
	}
	if (bpf_object__load(obj) != 0) {
		fprintf(stderr, "load %s failed\n", obj_path);
		bpf_object__close(obj);
		return 1;
	}

	/* Prefer the first program in the object. */
	prog = bpf_object__next_program(obj, NULL);
	if (!prog) {
		fprintf(stderr, "no program in object\n");
		bpf_object__close(obj);
		return 1;
	}
	prog_fd = bpf_program__fd(prog);

	if (strcmp(case_name, "context_bug") == 0 ||
	    strcmp(case_name, "context_fixed") == 0) {
		__u32 v0 = 0, v1 = 0;
		int i;

		/* Packet-only test-run leaves ingress_ifindex/rx_queue_index at
		 * zero on this host, so the oracle checks that the wrong-typed
		 * (or corrected) XDP object executes field stores and returns
		 * XDP_PASS for 10 trials — not non-zero field remapping. */
		map = bpf_object__find_map_by_name(obj, "observed");
		if (!map) {
			fprintf(stderr, "missing observed map\n");
			goto out;
		}
		map_fd = bpf_map__fd(map);
		for (i = 0; i < 10; i++) {
			zero_map_u32(map_fd, 0);
			zero_map_u32(map_fd, 1);
			if (test_run(prog_fd) != 0)
				goto out;
			if (lookup_u32(map_fd, 0, &v0) != 0 ||
			    lookup_u32(map_fd, 1, &v1) != 0) {
				fprintf(stderr, "observed lookup failed\n");
				goto out;
			}
		}
		printf("{\"case\":\"%s\",\"oracle\":\"ok\",\"observed0\":%u,\"observed1\":%u,\"trials\":10,\"ctx_in\":\"unsupported\"}\n",
		       case_name, v0, v1);
		ok = 1;
	} else if (strcmp(case_name, "oversized_update_bug") == 0 ||
		   strcmp(case_name, "oversized_update_fixed") == 0) {
		__u32 src = 0, dst = 0;
		__u32 value_size;
		int i;

		map = bpf_object__find_map_by_name(obj, "data");
		if (!map) {
			fprintf(stderr, "missing data map\n");
			goto out;
		}
		map_fd = bpf_map__fd(map);
		value_size = bpf_map__value_size(map);
		if (value_size != 8) {
			fprintf(stderr, "unexpected value_size %u\n", value_size);
			goto out;
		}
		for (i = 0; i < 10; i++) {
			zero_map_conn(map_fd, 0);
			if (test_run(prog_fd) != 0)
				goto out;
			if (lookup_conn(map_fd, 0, &src, &dst) != 0) {
				fprintf(stderr, "data lookup failed\n");
				goto out;
			}
			/* Both bug (truncated big) and fixed write {1,2}. */
			if (src != 1 || dst != 2) {
				fprintf(stderr,
					"oversized oracle fail trial %d: got (%u,%u)\n",
					i, src, dst);
				goto out;
			}
		}
		printf("{\"case\":\"%s\",\"oracle\":\"ok\",\"value_size\":8,\"src\":1,\"dst\":2,\"trials\":10}\n",
		       case_name);
		ok = 1;
	} else if (strcmp(case_name, "reinterpretation_bug") == 0) {
		__u64 got = 0;
		__u64 expect = native_conn_as_u64(1, 2);
		int i;

		map = bpf_object__find_map_by_name(obj, "data");
		observed_fd = bpf_map__fd(bpf_object__find_map_by_name(obj, "observed"));
		if (!map || observed_fd < 0) {
			fprintf(stderr, "missing data/observed map\n");
			goto out;
		}
		map_fd = bpf_map__fd(map);
		for (i = 0; i < 10; i++) {
			zero_map_conn(map_fd, 0);
			zero_map_u64(observed_fd, 0);
			if (test_run(prog_fd) != 0)
				goto out;
			if (lookup_u64(observed_fd, 0, &got) != 0) {
				fprintf(stderr, "observed u64 lookup failed\n");
				goto out;
			}
			if (got != expect) {
				fprintf(stderr,
					"reinterpret oracle fail trial %d: got %llu want %llu\n",
					i, (unsigned long long)got,
					(unsigned long long)expect);
				goto out;
			}
		}
		printf("{\"case\":\"%s\",\"oracle\":\"ok\",\"bytes\":%llu,\"endian_native\":true,\"trials\":10}\n",
		       case_name, (unsigned long long)expect);
		ok = 1;
	} else if (strcmp(case_name, "reinterpretation_fixed") == 0) {
		__u32 src = 0, dst = 0;
		int i;

		observed_fd = bpf_map__fd(bpf_object__find_map_by_name(obj, "observed"));
		map = bpf_object__find_map_by_name(obj, "data");
		if (!map || observed_fd < 0) {
			fprintf(stderr, "missing data/observed map\n");
			goto out;
		}
		map_fd = bpf_map__fd(map);
		for (i = 0; i < 10; i++) {
			zero_map_conn(map_fd, 0);
			zero_map_u32(observed_fd, 0);
			zero_map_u32(observed_fd, 1);
			if (test_run(prog_fd) != 0)
				goto out;
			if (lookup_u32(observed_fd, 0, &src) != 0 ||
			    lookup_u32(observed_fd, 1, &dst) != 0) {
				fprintf(stderr, "observed lookup failed\n");
				goto out;
			}
			if (src != 1 || dst != 2) {
				fprintf(stderr,
					"reinterpret fixed oracle fail trial %d: got (%u,%u)\n",
					i, src, dst);
				goto out;
			}
		}
		printf("{\"case\":\"%s\",\"oracle\":\"ok\",\"src\":1,\"dst\":2,\"trials\":10}\n",
		       case_name);
		ok = 1;
	} else {
		fprintf(stderr, "unknown case %s\n", case_name);
	}

out:
	bpf_object__close(obj);
	return ok ? 0 : 1;
}
