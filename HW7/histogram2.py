# Copyright 2014 Dr. Greg M. Bernstein
""" A simple script that uses the Python *random* library and the *matplotlib*
    library to create histogram of exponentially distributed random numbers.
"""

import random
import matplotlib.pyplot as plt

if __name__ == '__main__':
    # Generate a list of samples
    # This technique is called a "list comprehension" in Python
    normSamples = [random.normalvariate(9.0, 2.0) for i in range(100000)]
    print(normSamples[0:10])  #Take a look at the first 10
    fig, axis = plt.subplots()
    axis.hist(normSamples, bins=100, normed=True)
    axis.set_title(r"Histogram of an Normal RNG $\mu = 9$ and $\sigma = 2$")
    axis.set_xlabel("x")
    axis.set_ylabel("normalized frequency of occurrence")
    fig.savefig("ExponentialHistogram.png")
    plt.show()
