# Offline kernel benchmarks

[Русская версия](BENCHMARKS.ru.md)

25 October 2026, Python 3.14.5, macOS 27.0.1 ARM64. Three repetitions; the table reports the median. Data are synthetic: numeric descriptors for straight edges with five lengths and two directions.

| Candidates + example | Separate hypotheses, ms | Shared ranking, ms | Pair of range steps, ms |
| --- | ---: | ---: | ---: |
| 100 + 1 | 0.352 | 0.379 | 0.018 |
| 1,000 + 1 | 3.295 | 3.609 | 0.021 |
| 10,000 + 1 | 32.475 | 36.609 | 0.029 |

These are not Fusion latencies. The measurement excludes BRep reading, CustomGraphics construction, application keyboard handling, and viewport redraw. The pair of steps measures range changes on an already prepared ranking, without extracting features again.

To reproduce:

```sh
python scripts/benchmark_offline.py --repeats 3
```

In a live control session, `tests/fusion_read_contract.py` checked 97 edges and 39 faces with eight examples of each type in approximately 0.03 seconds. This is a limited read-only contract on one model, not a general CAD benchmark.
