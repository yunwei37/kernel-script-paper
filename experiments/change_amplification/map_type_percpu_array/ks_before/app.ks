var counts : array<u32, u64>(1)

@perf_event
fn count_fault(ctx: *bpf_perf_event_data) -> i32 {
  counts[0] = counts[0] + 1
  return 0
}

fn main() -> i32 {
  var prog = load(count_fault)
  var link = attach(prog, perf_options { event: page_faults, pid: 0, cpu: -1, period: 1 }, 0)
  var total = counts[0]
  print("count=%llu", total)
  detach(link)
  detach(prog)
  return 0
}
