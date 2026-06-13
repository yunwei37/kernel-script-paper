include "../../kernelscript/examples/xdp.kh"

@tc("ingress")
fn bad_tc(ctx: *xdp_md) -> i32 {
  return 0
}
