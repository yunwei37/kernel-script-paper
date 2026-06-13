include "../../kernelscript/examples/xdp.kh"

var counts : hash<u32, u64>(16)

@xdp
fn bad_key(ctx: *xdp_md) -> xdp_action {
  counts["bad"] = 1
  return XDP_PASS
}
