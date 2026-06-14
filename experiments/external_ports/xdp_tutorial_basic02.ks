include "../../kernelscript/examples/xdp.kh"

@xdp fn xdp_pass_func(ctx: *xdp_md) -> xdp_action {
  return XDP_PASS
}

@xdp fn xdp_drop_func(ctx: *xdp_md) -> xdp_action {
  return XDP_DROP
}

fn main() -> i32 {
  var prog = load(xdp_pass_func)
  attach(prog, "lo", 0)
  detach(prog)
  return 0
}
