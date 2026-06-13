include "../../kernelscript/examples/xdp.kh"

@xdp
fn bad_return(ctx: *xdp_md) -> i32 {
  return 0
}
