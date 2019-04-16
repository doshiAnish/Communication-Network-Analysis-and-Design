"""
This file shows an example of a traffic shaper whose bucket size is
a multiple of the packet size and whose bucket rate is very slow compared
to the input.

Copyright Dr. Greg M. Bernstein 2014
Released under the MIT license
"""
import simpy
import matplotlib.pyplot as plt

from SimComponents import PacketGenerator, PacketSink, ShaperTokenBucket


import simpy
import matplotlib.pyplot as plt
from SimComponents import PacketGenerator, PacketSink, ShaperTokenBucket

# You need to create the pattern "generator"
mygen = myPattern()
mygen2 = myPattern()

def arrivals1():
    return next(mygen)

def arrivals2():
    return next(mygen2)

def const_size():
    return 200.0

env = simpy.Environment()
# Create two identical packet generators based on your pattern
# one will go through a shaper and one will not
pg = PacketGenerator(env, "CSU", arrivals1, const_size, initial_delay=0.0, finish=60)
pg2 = PacketGenerator(env, "EB", arrivals2, const_size, initial_delay=0.0, finish=60)

# Two packet sinks to measure the arrival times
ps = PacketSink(env, rec_arrivals=True, absolute_arrivals=True)
ps2 = PacketSink(env, rec_arrivals=True, absolute_arrivals=True)

bucket_rate = # You need to fill this in
bucket_size = # You need to fill this in
shaper = ShaperTokenBucket(env, bucket_rate, bucket_size)
pg.out = ps
pg2.out = shaper
shaper.out = ps2
env.run(until=10000)
print(ps.arrivals)

fig, axis = plt.subplots()
axis.vlines(ps.arrivals, 0.0, 1.0, colors="g", linewidth=2.0, linestyles='--', label='input stream')
axis.vlines(ps2.arrivals, 0.0, 0.7, colors="r", linewidth=2.0, label='output stream')
axis.set_title("Arrival times")
axis.set_xlabel("time")
axis.set_ylim([0, 1.2])
axis.set_xlim([0, 60])
axis.legend()
plt.show()