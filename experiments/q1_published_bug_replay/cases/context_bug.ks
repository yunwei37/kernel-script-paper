// Heimdall Listing 5: @xdp entry with TC context type.
// Expected diagnostic: @xdp attributed function must have signature ...
include "../headers/xdp.kh"
include "../headers/sk_buff.kh"

var observed : array<u32, u32>(2)

@xdp fn monitor_packets(ctx: *__sk_buff) -> xdp_action {
  observed[0] = ctx->protocol
  observed[1] = ctx->queue_mapping
  return XDP_PASS
}

fn main() -> i32 {
  return 0
}
