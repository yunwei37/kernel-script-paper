// Heimdall Listing 6 BUG 1: 16-byte value into 8-byte map slot.
// Expected diagnostic: Map value type mismatch
include "../headers/xdp.kh"

struct Conn {
  src_ip: u32,
  dst_ip: u32,
}

struct Big {
  a: u32,
  b: u32,
  c: u32,
  d: u32,
}

var data : array<u32, Conn>(1)

@xdp fn map_schema_bug(ctx: *xdp_md) -> xdp_action {
  data[0] = Big { a: 1, b: 2, c: 3, d: 4 }
  return XDP_PASS
}

fn main() -> i32 {
  return 0
}
