include "../../kernelscript/examples/tcp_congestion_ops.kh"

var callback_flags : array<u32, u32>(5)

@struct_ops("tcp_congestion_ops")
impl minimal_congestion_control {
    fn ssthresh(sk: *u8) -> u32 {
        callback_flags[0] = 1
        return 16
    }

    fn undo_cwnd(sk: *u8) -> u32 {
        callback_flags[1] = 1
        return ssthresh(sk)
    }

    fn cong_avoid(sk: *u8, ack: u32, acked: u32) -> void {
        callback_flags[2] = 1
    }

    fn set_state(sk: *u8, new_state: u8) -> void {
        callback_flags[3] = 1
    }

    fn cwnd_event(sk: *u8, ev: u32) -> void {
        callback_flags[4] = 1
    }
}

fn main() -> i32 {
    var result = register(minimal_congestion_control)
    return result
}
