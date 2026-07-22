// Heimdall Listing 6 BUG 2: reinterpret map value as unrelated type.
// Expected diagnostic: Type mismatch in declaration
include "../headers/xdp.kh"

struct Conn {
  src_ip: u32,
  dst_ip: u32,
}

struct Stats {
  bytes: u64,
}

var data : array<u32, Conn>(1)

@xdp fn map_schema_bug(ctx: *xdp_md) -> xdp_action {
  data[0] = Conn { src_ip: 1, dst_ip: 2 }
  var stats: Stats = data[0]
  return XDP_PASS
}

fn main() -> i32 {
  return 0
}
