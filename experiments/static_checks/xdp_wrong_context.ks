include "../../kernelscript/examples/xdp.kh"
include "../../kernelscript/examples/tc.kh"

@xdp
fn bad_xdp(ctx: *__sk_buff) -> xdp_action {
  return XDP_PASS
}
