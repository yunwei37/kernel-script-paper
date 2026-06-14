@perf_event
fn on_event(ctx: *bpf_perf_event_data) -> i32 {
  return 0
}

fn main() -> i32 {
  var prog = load(on_event)
  var leader = attach(prog, perf_options { perf_type: perf_type_software, perf_config: page_faults }, 0)
  var sw0 = attach(prog, perf_options { perf_type: perf_type_software, perf_config: context_switches, group: leader }, 0)
  var sw1 = attach(prog, perf_options { perf_type: perf_type_software, perf_config: context_switches, group: leader }, 0)
  var sw2 = attach(prog, perf_options { perf_type: perf_type_software, perf_config: context_switches, group: leader }, 0)
  var sw3 = attach(prog, perf_options { perf_type: perf_type_software, perf_config: context_switches, group: leader }, 0)
  var sw4 = attach(prog, perf_options { perf_type: perf_type_software, perf_config: context_switches, group: leader }, 0)
  var sw5 = attach(prog, perf_options { perf_type: perf_type_software, perf_config: context_switches, group: leader }, 0)
  var sw6 = attach(prog, perf_options { perf_type: perf_type_software, perf_config: context_switches, group: leader }, 0)
  var sw7 = attach(prog, perf_options { perf_type: perf_type_software, perf_config: context_switches, group: leader }, 0)
  var sw8 = attach(prog, perf_options { perf_type: perf_type_software, perf_config: context_switches, group: leader }, 0)
  var sw9 = attach(prog, perf_options { perf_type: perf_type_software, perf_config: context_switches, group: leader }, 0)
  var sw10 = attach(prog, perf_options { perf_type: perf_type_software, perf_config: context_switches, group: leader }, 0)
  var sw11 = attach(prog, perf_options { perf_type: perf_type_software, perf_config: context_switches, group: leader }, 0)
  var sw12 = attach(prog, perf_options { perf_type: perf_type_software, perf_config: context_switches, group: leader }, 0)
  var sw13 = attach(prog, perf_options { perf_type: perf_type_software, perf_config: context_switches, group: leader }, 0)
  var sw14 = attach(prog, perf_options { perf_type: perf_type_software, perf_config: context_switches, group: leader }, 0)
  var sw15 = attach(prog, perf_options { perf_type: perf_type_software, perf_config: context_switches, group: leader }, 0)
  detach(sw15)
  detach(sw14)
  detach(sw13)
  detach(sw12)
  detach(sw11)
  detach(sw10)
  detach(sw9)
  detach(sw8)
  detach(sw7)
  detach(sw6)
  detach(sw5)
  detach(sw4)
  detach(sw3)
  detach(sw2)
  detach(sw1)
  detach(sw0)
  detach(leader)
  detach(prog)
  return 0
}
