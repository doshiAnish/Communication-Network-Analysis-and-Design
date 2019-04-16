"""
Example of a two rate three color marker (trTCM).

"""

import simpy
import matplotlib.pyplot as plt

from SimComponents import PacketGenerator, PacketSink, FlowDemux, TrTCM




if __name__ == '__main__':
    def const_arrival():
        return 3.0  # 1.0 => 12Gbps, 5 => 2.4Gbps 3 => 4Gbps

    def const_size():
        return 1500.0

    pir = 6000.0  # 6Gbps
    pbs = 3000  # bytes
    cir = 3000.0  # 3Gbps
    cbs = 4000  # bytes

    env = simpy.Environment()
    pg = PacketGenerator(env, "SJSU", const_arrival, const_size)
    ps_green = PacketSink(env, rec_arrivals=True, absolute_arrivals=True)
    ps_yellow = PacketSink(env, rec_arrivals=True, absolute_arrivals=True)
    ps_red = PacketSink(env, rec_arrivals=True, absolute_arrivals=True)
    marker = TrTCM(env, pir, pbs, cir, cbs)
    demux = FlowDemux([ps_green, ps_yellow, ps_red])
    pg.out = marker
    marker.out = demux
    env.run(until=50)

    fig, ax1 = plt.subplots()
    ax1.vlines(ps_green.arrivals, 0.0, 1.0, colors="g", linewidth=2.0, label='green')
    ax1.vlines(ps_yellow.arrivals, 0.0, 0.8, colors="y", linewidth=2.0, linestyles='--', label='yellow')
    ax1.vlines(ps_red.arrivals, 0.0, 0.6, colors="r", linewidth=2.0, label='red')
    ax1.set_title("trTCM marking")
    ax1.set_xlabel("time")
    ax1.set_ylim([0, 1.5])
    ax1.legend()
    plt.show()
