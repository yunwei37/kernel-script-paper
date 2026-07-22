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

var observed : array<u32, u32>(2)

@xdp fn monitor_packets(ctx: *xdp_md) -> xdp_action {
  observed[0] = ctx->rx_queue_index
  observed[1] = ctx->ingress_ifindex
  return XDP_PASS
}

fn main() -> i32 {
  return 0
}
