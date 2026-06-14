include "../../kernelscript/examples/xdp.kh"

struct TestData {
  value: u64,
}

@xdp
fn bad_xdp(ctx: *xdp_md) -> xdp_action {
  var ptr = new TestData(GFP_ATOMIC)
  delete ptr
  return XDP_PASS
}

fn main() -> i32 {
  var prog = load(bad_xdp)
  attach(prog, "lo", 0)
  detach(prog)
  return 0
}
