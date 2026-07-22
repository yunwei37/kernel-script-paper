// Corrected control for Heimdall Listing 5.
include "../headers/xdp.kh"

var observed : array<u32, u32>(2)

@xdp fn monitor_packets(ctx: *xdp_md) -> xdp_action {
  observed[0] = ctx->rx_queue_index
  observed[1] = ctx->ingress_ifindex
  return XDP_PASS
}

fn main() -> i32 {
  return 0
}
