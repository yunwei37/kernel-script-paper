// Injected mistake: @xdp entry point declared with a *__sk_buff context
// instead of *xdp_md. Base program is the working XDP map-counter.
// Coupling: signature / domain. Expected: KernelScript rejects at compile.
include "../../kernelscript/examples/xdp.kh"
include "../../kernelscript/examples/tc.kh"

var counts : array<u32, u64>(1)

@xdp
fn count_pass(ctx: *__sk_buff) -> xdp_action {
  counts[0] = counts[0] + 1
  return XDP_PASS
}

fn main() -> i32 {
  var prog = load(count_pass)
  attach(prog, "lo", 0)
  detach(prog)
  return 0
}
