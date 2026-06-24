include "../../kernelscript/examples/xdp.kh"

@helper
fn should_drop() -> bool {
    return true
}

@xdp
fn drop_handler(ctx: *xdp_md) -> xdp_action {
    return XDP_DROP
}

@xdp
fn packet_filter(ctx: *xdp_md) -> xdp_action {
    if (should_drop()) {
        return drop_handler(ctx)
    }
    return XDP_PASS
}
