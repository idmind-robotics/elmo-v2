#! /usr/bin/env python


import matplotlib.pyplot as plt


times = []
values = []

with open("/home/idmind/battery_log.csv") as fp:
  lines = fp.readlines()[1:]
  for line in lines:
    t, value = line.split(",")
    values.append(float(value))
    times.append(t.split(" ")[1].split(".")[0])


# plt.scatter(range(len(values)), values)
plt.scatter(times, values)
plt.show()
