// Corrected control for Heimdall Listing 6 BUG 1.
include "../headers/xdp.kh"

struct Conn {
  src_ip: u32,
  dst_ip: u32,
}

var data : array<u32, Conn>(1)

@xdp fn map_schema_fixed(ctx: *xdp_md) -> xdp_action {
  data[0] = Conn { src_ip: 1, dst_ip: 2 }
  return XDP_PASS
}

fn main() -> i32 {
  return 0
}
