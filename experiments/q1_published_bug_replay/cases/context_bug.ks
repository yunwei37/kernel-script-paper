struct xdp_md {
  data: u32,
  data_end: u32,
  data_meta: u32,
  ingress_ifindex: u32,
  rx_queue_index: u32,
  egress_ifindex: u32,
}

struct __sk_buff {
  len: u32,
  pkt_type: u32,
  mark: u32,
  queue_mapping: u32,
  protocol: u32,
}

enum xdp_action {
  XDP_ABORTED = 0,
  XDP_DROP = 1,
  XDP_PASS = 2,
  XDP_TX = 3,
  XDP_REDIRECT = 4,
}

@xdp fn monitor_packets(ctx: *__sk_buff) -> xdp_action {
  var protocol = ctx->protocol
  var queue_mapping = ctx->queue_mapping
  return XDP_PASS
}

fn main() -> i32 {
  return 0
}
