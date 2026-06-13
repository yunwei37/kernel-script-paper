include "../../kernelscript/examples/xdp.kh"

var counts : hash<u32, u64>(16)

@xdp
fn bad_value(ctx: *xdp_md) -> xdp_action {
  counts[1] = "bad"
  return XDP_PASS
}
