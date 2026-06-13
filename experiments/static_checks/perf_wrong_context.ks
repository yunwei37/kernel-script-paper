include "../../kernelscript/examples/xdp.kh"

@perf_event
fn on_event(ctx: *xdp_md) -> i32 {
  return 0
}

fn main() -> i32 {
  var prog = load(on_event)
  return 0
}
