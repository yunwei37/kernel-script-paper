include "../../kernelscript/examples/xdp.kh"

enum IpProtocol {
    ICMP = 1,
    TCP = 6,
    UDP = 17
}

@helper
fn get_ip_protocol(ctx: *xdp_md) -> u32 {
    return 6
}

@helper
fn get_tcp_dest_port(ctx: *xdp_md) -> u32 {
    return 80
}

@helper
fn get_udp_dest_port(ctx: *xdp_md) -> u32 {
    return 53
}

@xdp
fn packet_classifier(ctx: *xdp_md) -> xdp_action {
    var protocol = get_ip_protocol(ctx)

    if (protocol == TCP) {
        var port = get_tcp_dest_port(ctx)
        return match (port) {
            80: XDP_PASS,
            443: XDP_PASS,
            22: XDP_PASS,
            21: XDP_DROP,
            23: XDP_DROP,
            default: XDP_PASS
        }
    }

    if (protocol == UDP) {
        var port = get_udp_dest_port(ctx)
        return match (port) {
            53: XDP_PASS,
            123: XDP_PASS,
            161: XDP_DROP,
            69: XDP_DROP,
            default: XDP_PASS
        }
    }

    if (protocol == ICMP) {
        return XDP_DROP
    }

    return XDP_ABORTED
}
