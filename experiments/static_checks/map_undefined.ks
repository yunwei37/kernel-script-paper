include "../../kernelscript/examples/xdp.kh"

@xdp
fn bad_map(ctx: *xdp_md) -> xdp_action {
  missing_map[1] = 42
  return XDP_PASS
}
