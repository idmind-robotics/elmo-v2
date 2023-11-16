#! /usr/bin/env python


import matplotlib.pyplot as plt


times = []
values = []

with open("/home/idmind/battery_log.csv") as fp:
  lines = fp.readlines()[1:]
  for line in lines:
    t, value = line.split(",")
    values.append(float(value))
    times.append(t.split(" ")[1].split(".")[0][:-3])

time_ticks = []
for idx, t in enumerate(times):
  if idx % 5 == 0:
    time_ticks.append(t)

# plt.scatter(range(len(values)), values)
plt.scatter(times, values)
plt.ylim(10.0, 18.0)
plt.xticks(time_ticks, rotation=45, ha="right")
plt.grid(True, linestyle='--', alpha=0.7)
plt.tight_layout()
plt.show()
