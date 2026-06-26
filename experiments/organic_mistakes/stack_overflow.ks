// Injected mistake: a 600-byte on-stack buffer pushes the eBPF program over
// the 512-byte stack limit. Base program is the working XDP map-counter.
// Coupling: safety (a verifier-class check moved earlier). Expected:
// KernelScript rejects at compile via safety analysis; C compiles and the
// kernel verifier rejects it at load.
include "../../kernelscript/examples/xdp.kh"

var counts : array<u32, u64>(1)

@xdp
fn count_pass(ctx: *xdp_md) -> xdp_action {
  counts[0] = counts[0] + 1
  var large_buffer: u8[600] = [0]
  large_buffer[0] = 1
  return XDP_PASS
}

fn main() -> i32 {
  var prog = load(count_pass)
  attach(prog, "lo", 0)
  detach(prog)
  return 0
}
