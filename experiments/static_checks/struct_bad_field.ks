include "../../kernelscript/examples/xdp.kh"

struct Config {
  value: u32,
}

@helper
fn read_config(cfg: Config) -> u32 {
  return cfg.missing_field
}

@xdp
fn use_config(ctx: *xdp_md) -> xdp_action {
  return XDP_PASS
}
