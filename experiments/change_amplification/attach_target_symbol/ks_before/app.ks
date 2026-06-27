@probe("do_exit")
fn trace_target(code: i64) -> i32 {
  return 0
}

fn main() -> i32 {
  var prog = load(trace_target)
  attach(prog, "do_exit", 0)
  detach(prog)
  return 0
}
