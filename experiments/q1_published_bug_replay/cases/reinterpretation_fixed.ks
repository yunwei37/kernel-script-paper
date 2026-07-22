// Corrected control for Heimdall Listing 6 BUG 2.
// Writes observed fields so the shared runtime oracle can check them.
include "../headers/xdp.kh"

struct Conn {
  src_ip: u32,
  dst_ip: u32,
}

var data : array<u32, Conn>(1)
var observed : array<u32, u32>(2)

@xdp fn map_schema_fixed(ctx: *xdp_md) -> xdp_action {
  data[0] = Conn { src_ip: 1, dst_ip: 2 }
  var conn: Conn = data[0]
  observed[0] = conn.src_ip
  observed[1] = conn.dst_ip
  return XDP_PASS
}

fn main() -> i32 {
  return 0
}
