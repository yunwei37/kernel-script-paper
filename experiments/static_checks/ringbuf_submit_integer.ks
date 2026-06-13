include "../../kernelscript/examples/xdp.kh"

struct Event {
  marker: u32,
}

var events : ringbuf<Event>(4096)

@xdp
fn bad_submit(ctx: *xdp_md) -> xdp_action {
  events.submit(42)
  return XDP_PASS
}
