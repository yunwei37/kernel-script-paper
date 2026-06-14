include "../../kernelscript/examples/xdp.kh"

@xdp fn xdp_prog_simple(ctx: *xdp_md) -> xdp_action {
  return XDP_PASS
}

fn main() -> i32 {
  var prog = load(xdp_prog_simple)
  attach(prog, "lo", 0)
  detach(prog)
  return 0
}
