@probe("sys_openat")
fn bad_probe(dfd: i32) -> u32 {
  return 0
}
