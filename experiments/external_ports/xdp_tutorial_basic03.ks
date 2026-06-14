include "../../kernelscript/examples/xdp.kh"

struct DataRec {
  rx_packets: u64,
}

var xdp_stats_map : array<u32, DataRec>(5)

@xdp fn xdp_stats1_func(ctx: *xdp_md) -> xdp_action {
  var key = XDP_PASS

  if (var rec = xdp_stats_map[key]) {
    rec.rx_packets = rec.rx_packets + 1
  } else {
    xdp_stats_map[key] = DataRec {
      rx_packets: 1,
    }
  }

  return XDP_PASS
}

fn main() -> i32 {
  var prog = load(xdp_stats1_func)
  attach(prog, "lo", 0)
  detach(prog)
  return 0
}
