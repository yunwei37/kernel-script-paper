@perf_event
fn count_samples(ctx: *bpf_perf_event_data) -> i32 {
  return 0
}

fn main() -> i32 {
  var prog = load(count_samples)
  var cache = attach(prog, perf_options { event: cache_misses, period: 1000000 }, 0)
  var total = read(cache).scaled
  print("cache=%lld", total)
  detach(cache)
  detach(prog)
  return 0
}
