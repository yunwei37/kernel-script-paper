@helper
fn kernel_helper(x: u32) -> u32 {
  return x + 1
}

fn main() -> i32 {
  var result = kernel_helper(41)
  return 0
}
