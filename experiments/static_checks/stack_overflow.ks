include "../../kernelscript/examples/xdp.kh"

@xdp
fn too_much_stack(ctx: *xdp_md) -> xdp_action {
  var large_buffer: u8[600] = [0]
  large_buffer[0] = 1
  return XDP_PASS
}
