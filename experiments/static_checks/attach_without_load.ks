include "../../kernelscript/examples/xdp.kh"

@xdp
fn pass_all(ctx: *xdp_md) -> xdp_action {
  return XDP_PASS
}

fn main() -> i32 {
  attach(pass_all, "lo", 0)
  return 0
}
