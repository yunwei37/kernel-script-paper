// Injected mistake: store a string into a map whose value type is u64.
// Base program is the working XDP map-counter.
// Coupling: representation. Expected: KernelScript rejects at compile
// (map value type mismatch); C compiles with a warning and the bad value
// reaches the kernel undetected.
include "../../kernelscript/examples/xdp.kh"

var counts : array<u32, u64>(1)

@xdp
fn count_pass(ctx: *xdp_md) -> xdp_action {
  counts[0] = "bad"
  return XDP_PASS
}

fn main() -> i32 {
  var prog = load(count_pass)
  attach(prog, "lo", 0)
  detach(prog)
  return 0
}
