include "../../kernelscript/examples/xdp.kh"

@helper
fn read_unknown(cfg: MissingStruct) -> u32 {
  return cfg.value
}

@xdp
fn use_unknown(ctx: *xdp_md) -> xdp_action {
  return XDP_PASS
}
