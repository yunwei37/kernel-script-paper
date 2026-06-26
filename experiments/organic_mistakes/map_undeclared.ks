// Injected mistake: the entry point reads/writes a map that was never
// declared (typo for `counts`). Base program is the working XDP map-counter.
// Coupling: representation. Expected: KernelScript rejects at compile
// (undefined symbol); C also rejects at clang (undeclared identifier) -- a tie.
include "../../kernelscript/examples/xdp.kh"

var counts : array<u32, u64>(1)

@xdp
fn count_pass(ctx: *xdp_md) -> xdp_action {
  missing_counts[0] = missing_counts[0] + 1
  return XDP_PASS
}

fn main() -> i32 {
  var prog = load(count_pass)
  attach(prog, "lo", 0)
  detach(prog)
  return 0
}
