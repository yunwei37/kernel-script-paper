include "../../kernelscript/examples/xdp.kh"

config settings {
  limit: u32,
}

@xdp
fn write_config(ctx: *xdp_md) -> xdp_action {
  settings.limit = 1
  return XDP_PASS
}
