struct xdp_md {
  data: u32,
  data_end: u32,
  data_meta: u32,
  ingress_ifindex: u32,
  rx_queue_index: u32,
  egress_ifindex: u32,
}

enum xdp_action {
  XDP_ABORTED = 0,
  XDP_DROP = 1,
  XDP_PASS = 2,
  XDP_TX = 3,
  XDP_REDIRECT = 4,
}

struct Conn {
  src_ip: u32,
  dst_ip: u32,
}

var data : array<u32, Conn>(1)

@xdp fn map_schema_fixed(ctx: *xdp_md) -> xdp_action {
  data[0] = Conn { src_ip: 1, dst_ip: 2 }
  var conn: Conn = data[0]
  return XDP_PASS
}

fn main() -> i32 {
  return 0
}
