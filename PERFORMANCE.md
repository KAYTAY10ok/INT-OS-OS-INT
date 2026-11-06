# INT Linux performance methodology

Status: measurement plan with verified functional smoke and minimal-console boots. No resource, boot-latency, or physical-hardware performance baseline has been collected. Numerical resource budgets must come from an actual baseline; the current cloud host's capacity is not a minimum requirement for running INT.

## Measurement contract

For every result, record the image checksum and source revision, kernel configuration, package/service manifest, firmware, CPU, RAM, storage, graphics, power mode, and measurement-tool versions. For QEMU, also record emulator version, acceleration mode, vCPU count, guest RAM, disk format, and host load. TCG and hardware acceleration results are separate test conditions.

Use the same settling period, workload, data set, display settings, and cache policy for comparisons. Repeat measurements, keep individual samples, and report sample count and spread. Distinguish cold and warm application starts. Record failures and missing sensors; never turn an unavailable metric into zero.

## Required measurements

| Area | Measurement and procedure | Suitable tools or data |
| --- | --- | --- |
| Boot | Kernel start to usable serial login; later firmware-to-login and usable desktop | Timestamped serial log, systemd-analyze where available |
| Idle memory | RAM, available memory, swap, and pressure after a fixed settling interval | `/proc/meminfo`, PSI, `smem` or equivalent when packaged |
| Idle CPU | Interval samples while the session is untouched; enumerate active services | `/proc/stat`, `pidstat`, service inventory |
| Desktop | Session startup, compositor resource use, interactive workload behavior | Session logs, process counters, repeatable input workload |
| Application launch | Command to usable application state, with explicit cache policy | Timed workload plus application-specific readiness probe |
| Memory pressure | Behavior under a bounded repeatable workload and recovery after it ends | PSI, swap activity, major faults, workload exit status |
| Scheduling | Latency and throughput with a documented mixed workload | `perf` and scheduler tools where permitted |
| Storage | Bounded I/O on a disposable test file, never a raw user disk | `fio` or equivalent, `iostat`, filesystem details |
| Network | Throughput and CPU cost between controlled endpoints | `iperf3`, interface counters, endpoint configuration |
| Packages | Download/verification/install time and peak resource use for a fixed signed package set | DNF/RPM logs, time/resource counters |
| Background services | Per-service CPU, memory, wakeups, and startup behavior | systemd and process/cgroup counters |

Choose tools already available in the image where practical. Monitoring must use bounded intervals and stop when the experiment ends; it must not become a permanent high-frequency polling service.

## Benchmark profiles

1. Kernel boot and serial console.
2. Minimal userspace and init.
3. INT-OS terminal profile.
4. INT-OS shared desktop.
5. OS-INT base.
6. OS-INT with one declared optional tool group.
7. Multiple simultaneous, authorized OS-INT workloads.

Keep a known-good image as the comparison baseline. Record which packages and services explain the difference between profiles. An unloaded desktop and an active security workload are different scenarios and must not be compared as equivalent idle measurements.

## Acceptance and optimization

The first foundation gate is functional: the selected image must boot, reach the expected readiness condition, and execute the intended checks without ignored failures. Measurement acceptance requires an identifiable artifact, documented method, completed runs, and preserved raw data.

Resource and latency budgets remain pending the first measured baseline. A budget must state its hardware tier, workload, measurement, and rationale. Do not invent performance percentages or publish a minimum RAM claim before measurement. A performance improvement is accepted only with a matching baseline and checks for security, reliability, and compatibility regressions. Kernel fragments, allocator changes, logging limits, and service removals require evidence just like desktop changes.

Virtual-machine measurements support development regressions under fixed conditions. They do not establish physical boot time, battery life, driver coverage, or desktop latency on real machines. See [hardware coverage](HARDWARE_COMPATIBILITY.md) for the required test classes.

## Verified functional result, not a performance baseline

The latest smoke run `qemu-smoke-20261105T170800.850984Z-60f2c0aae128` on 2026-11-05 passed all seven assertions for `int-image-smoke`. QEMU 8.2.2 used TCG, a `qemu64` CPU model, 2 virtual CPUs, and 512 MiB configured guest RAM; it exited 0 without timeout. That RAM setting is an input to the functional test, not a measured memory requirement.

The separate non-test image was observed in run `minimal-console-20261105T171144.595744Z-2c65869f558e` with the same emulator settings. Kernel startup, the INT banner, and a serial login prompt were observed; the manifest omits the smoke package and the serial log contains no smoke output. QEMU was stopped externally through QMP with exit 0. This does not verify password authentication or guest shutdown, and it is not a performance experiment.

The first successful smoke run `qemu-smoke-20261105T165955.205012Z-6c711ae0a6d6` remains historical evidence and reported **46.693 seconds elapsed**. Runner intervals include preparation, artifact copying/checks, guest execution, and shutdown; **they are not boot-time measurements**. No idle CPU/RAM, desktop, application-launch, storage-throughput, or physical-hardware result can be inferred from these records. The two earlier failed network-assertion runs remain failures and are not performance samples.

Each final run has its own directory under `/workspace/int-linux-work/evidence/`, retaining `result.json`, `serial.log`, `known-good.json`, and tested kernel/rootfs/manifest copies with matching SHA256 values. The builds and boots succeeded in the current workspace; restoration in a new task/machine and a repeatable performance baseline remain unverified.

## Results status

- [x] Measurement categories and reporting contract documented.
- [x] First functional QEMU smoke boot recorded with retained image and log evidence.
- [x] Separate minimal-image console boot recorded, with external emulator stop and its limited scope stated.
- [ ] First minimal-image performance baseline recorded with raw data.
- [ ] Numerical budgets derived from that baseline.
- [ ] Desktop and package-workflow baselines recorded.
- [ ] Three physical hardware classes measured.
- [ ] Any performance optimization verified against its baseline.

Actual measurements belong in `BENCHMARKS.md` with links to the underlying artifact and raw results. Leave the result explicitly unmeasured until the corresponding experiment has run.
