# dlp_mpi - Data-level parallelism with mpi for python

<table>
<tr>
<th>
Run an algorithm on multiple examples
</th>
<th>
Use dlp_mpi to run the loop body in parallel
</th>
</tr>
<tr>
<td>

```python
# python script.py

import time


examples = list(range(10))

for i in examples:
    # load, process and write data
    # for index i
    time.sleep(0.2)
    data = {'a': i}
    data['a'] += 2
    print(data)

    # Remember the results
    results.append(data['a'])










# Summarize your experiment
print(sum(results))
```
</td>
<td>

```python
# mpiexec -np 8 python script.py

import time
import dlp_mpi

examples = list(range(10))

for i in dlp_mpi.split_managed(examples):
    # load, process and write data
    # for index i
    time.sleep(0.2)
    data = {'a': i}
    data['a'] += 2
    print(data)

    # Remember the results
    results.append(data['a'])

results = dlp_mpi.gather(results)

if dlp_mpi.IS_MASTER:
results = [
    result
    for worker_results in results
    for result in worker_results
]

# Summarize your experiment
print(sum(results))
```
</td>
</tr>
</table>

This package uses `mpi4py` to provide utilities to parallize algorithms that are applied to multiple examples.

The core idea is: Start `N` processes and each process works in a subset of all examples.
To start the processes `mpiexec` can be used. Most HPC systems support MPI to scatter the workload across multiple hosts. For the command, look in the documentation for your HPC system and search for MPI launches.

Since each process should operate on different examples, MPI provides the variables `RANK` and `SIZE`, where `SIZE` is the number of workers and `RANK` is a unique identifier from `0` to `SIZE - 1`.
The simplest way to improve the execution time is to process `examples[RANK::SIZE]` on each worker.
This is a round robin load balancing (`dlp_mpi.split_round_robin`).
An more advanced load balaning is `dlp_mpi.split_managed`, where one process manages the load and assigns a new task to a worker, once he finishes the last task.

When in the end of a program all results should be summariesd or written in a single file, comunication between all processes is nessesary.
For this purpose `dlp_mpi.gather` (`mpi4py.MPI.COMM_WORLD.gather`) can be used. This function sends all data to the root process (For serialisation is `pickle` used).
