include "../../kernelscript/examples/tc.kh"

var counts : array<u32, u64>(1)

@tc("ingress")
fn count_ingress(ctx: *__sk_buff) -> i32 {
  counts[0] = counts[0] + 1
  return 0
}

fn main() -> i32 {
  var prog = load(count_ingress)
  attach(prog, "lo", 0)
  detach(prog)
  return 0
}
