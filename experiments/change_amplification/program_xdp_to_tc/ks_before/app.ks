include "../../../../kernelscript/examples/xdp.kh"

@xdp
fn pass_packet(ctx: *xdp_md) -> xdp_action {
  return XDP_PASS
}

fn main() -> i32 {
  var prog = load(pass_packet)
  attach(prog, "lo", 0)
  detach(prog)
  return 0
}
