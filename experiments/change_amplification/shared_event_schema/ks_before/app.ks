include "../../../../kernelscript/examples/xdp.kh"

struct PacketEvent {
  seq: u64,
}

var events : ringbuf<PacketEvent>(4096)

@xdp fn emit_event(ctx: *xdp_md) -> xdp_action {
  if (var reserved = events.reserve()) {
    reserved->seq = 1
    events.submit(reserved)
  }
  return XDP_PASS
}

fn handle_event(event: *PacketEvent) -> i32 {
  print("seq=%llu", event->seq)
  return 0
}

fn main() -> i32 {
  events.on_event(handle_event)
  var prog = load(emit_event)
  attach(prog, "lo", 0)
  dispatch(events)
  detach(prog)
  return 0
}
