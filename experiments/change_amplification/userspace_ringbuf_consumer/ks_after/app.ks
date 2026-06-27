include "../../../../kernelscript/examples/xdp.kh"

struct PacketEvent {
  seq: u64,
  marker: u32,
}

var events : ringbuf<PacketEvent>(4096)
var counts : array<u32, u64>(2)

@xdp fn count_packets(ctx: *xdp_md) -> xdp_action {
  if (var reserved = events.reserve()) {
    reserved->seq = counts[0]
    reserved->marker = 3203383023
    events.submit(reserved)
    counts[0] = counts[0] + 1
  } else {
    counts[1] = counts[1] + 1
  }
  return XDP_PASS
}

fn events_callback(event: *PacketEvent) -> i32 {
  print("seq=%llu marker=%u", event->seq, event->marker)
  return 0
}

fn main() -> i32 {
  events.on_event(events_callback)
  var prog = load(count_packets)
  attach(prog, "lo", 0)
  print("submitted=%llu", counts[0])
  dispatch(events)
  detach(prog)
  return 0
}
