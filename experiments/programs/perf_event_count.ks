var counts : array<u32, u64>(1)

@perf_event
fn count_page_fault(ctx: *bpf_perf_event_data) -> i32 {
  counts[0] = counts[0] + 1
  return 0
}

fn main() -> i32 {
  var prog = load(count_page_fault)
  var page = attach(prog, perf_options { perf_type: perf_type_software, perf_config: page_faults, pid: 0, cpu: -1, period: 1 }, 0)
  detach(page)
  detach(prog)
  return 0
}
