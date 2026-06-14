struct TestData {
  value: u64,
}

fn main() -> i32 {
  var ptr = new TestData(GFP_ATOMIC)
  delete ptr
  return 0
}
