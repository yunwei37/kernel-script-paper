include "../../kernelscript/examples/xdp.kh"

@helper
fn should_drop() -> bool {
    return true
}

@xdp
fn packet_filter(ctx: *xdp_md) -> xdp_action {
    if (should_drop()) {
        return XDP_DROP
    }
    return XDP_PASS
}
