@perf_event
fn on_event(ctx: *bpf_perf_event_data) -> i32 {
  return 0
}

fn main() -> i32 {
  var prog = load(on_event)
  var cache = attach(prog, perf_options { perf_type: perf_type_hardware, perf_config: cache_misses }, 0)
  var branch = attach(prog, perf_options { perf_type: perf_type_hardware, perf_config: branch_misses, group: cache }, 0)
  var cycles = attach(prog, perf_options { perf_type: perf_type_hardware, perf_config: cpu_cycles, group: cache }, 0)
  var inst = attach(prog, perf_options { perf_type: perf_type_hardware, perf_config: instructions, group: cache }, 0)
  var refs = attach(prog, perf_options { perf_type: perf_type_hardware, perf_config: cache_references, group: cache }, 0)
  detach(refs)
  detach(inst)
  detach(cycles)
  detach(branch)
  detach(cache)
  detach(prog)
  return 0
}
