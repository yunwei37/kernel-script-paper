include "../../kernelscript/examples/xdp.kh"

struct RingEvent {
  seq: u64,
  marker: u32,
}

var events : ringbuf<RingEvent>(1048576)
var counts : array<u32, u64>(2)

@xdp fn emit_event(ctx: *xdp_md) -> xdp_action {
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

fn main() -> i32 {
  var prog = load(emit_event)
  attach(prog, "lo", 0)
  detach(prog)
  return 0
}
