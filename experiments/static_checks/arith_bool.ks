include "../../kernelscript/examples/xdp.kh"

@xdp
fn bad_math(ctx: *xdp_md) -> xdp_action {
  var result = 42 + true
  return XDP_PASS
}
