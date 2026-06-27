include "../../../../kernelscript/examples/tc.kh"

@tc("ingress")
fn pass_packet(ctx: *__sk_buff) -> i32 {
  return 0
}

fn main() -> i32 {
  var prog = load(pass_packet)
  attach(prog, "lo", 0)
  detach(prog)
  return 0
}
