@perf_event
fn count_samples(ctx: *bpf_perf_event_data) -> i32 {
  return 0
}

fn main() -> i32 {
  var prog = load(count_samples)
  var cache = attach(prog, perf_options { event: cache_misses, period: 1000000 }, 0)
  var branch = attach(prog, perf_options { event: branch_misses, period: 1000000, group: cache }, 0)
  var snapshot = read(cache)
  print("cache=%lld branch=%lld entries=%u", read(cache).scaled, read(branch).scaled, snapshot.count)
  detach(branch)
  detach(cache)
  detach(prog)
  return 0
}
