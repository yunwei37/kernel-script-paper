include "../../kernelscript/examples/xdp.kh"

@xdp
fn main(ctx: *xdp_md) -> xdp_action {
  return XDP_PASS
}
