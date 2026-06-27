include "../../../../kernelscript/examples/xdp.kh"

struct PacketEvent {
  seq: u64,
  marker: u32,
}

var events : ringbuf<PacketEvent>(4096)

@xdp fn emit_event(ctx: *xdp_md) -> xdp_action {
  if (var reserved = events.reserve()) {
    reserved->seq = 1
    reserved->marker = 3203383023
    events.submit(reserved)
  }
  return XDP_PASS
}

fn handle_event(event: *PacketEvent) -> i32 {
  print("seq=%llu marker=%u", event->seq, event->marker)
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
