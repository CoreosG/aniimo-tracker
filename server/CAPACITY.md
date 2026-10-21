# Initial relay measurements — 21 October 2026

Measured against a separate loopback relay on the default VPS, alongside the
existing applications. The relay container was limited to 1.5 CPUs and 512 MiB
RAM. The load generator ran in a different container on the same six-vCPU,
approximately 24-GiB machine. These are short synthetic tests, not a production
capacity guarantee or an internet/Cloudflare benchmark.

| Workload | Active time | Disconnects | Delivery p50 | Delivery p95 | Receiver throughput |
| --- | --- | --- | --- | --- | --- |
| 3,000 clients / 1,000 parties, sending positions up to twice/sec | 20 sec | 0 | 1,000 ms | 1,680 ms | 0.681 MiB/sec |

Repeated coordinates are excluded from latency samples. Delivery times measure
new observed position samples, including batching and scheduling. Coalescing
intentionally replaces intermediate positions under load. The generator also
shares the machine, so these results include its scheduling overhead.

A separate earlier 3,000-client run sampled the relay at approximately 101 MiB
RAM and one CPU core in use. The desktop normally publishes at most once every
750 ms and sends nothing when there is no new position/evidence/profile update.
That is lighter than this test's twice/sec active workload.

Default admission remains bounded at 1,000 rooms and 3,200 sockets. At the tested
upper load, position delivery can take around two seconds before internet and
screen-recognition delays. Lower admission or update rates if the desired
latency is tighter. Longer soak tests, real geographic traffic and proxy memory
measurements are still needed before claiming sustained production capacity.
