include "../../kernelscript/examples/xdp.kh"

var counts : array<u32, u64>(1)

@xdp fn count_pass(ctx: *xdp_md) -> xdp_action {
  counts[0] = counts[0] + 1
  return XDP_PASS
}

fn main() -> i32 {
  var prog = load(count_pass)
  attach(prog, "lo", 0)
  detach(prog)
  return 0
}
