# Concurrency review checklist

Load when changed code involves async execution, concurrency, or shared
mutable state, in any repository. Translate each pattern to the PR's language.

## Pattern categories

- **Leak**: background work, channels, goroutines, tasks, or timers that can
  outlive their owner or never exit.
- **Race**: shared mutable state without synchronization; check-then-act
  sequences; non-atomic read-modify-write.
- **Deadlock / lock order**: multiple locks or maps acquired in inconsistent
  order; re-entrancy assumptions that do not hold.
- **Atomicity of compound operations**: DDL plus cache invalidation,
  timestamp updates, two-phase state changes that can interleave.
- **Cancellation / timeout**: work continuing after cancellation; deadlines
  applied to only part of a compound operation.
- **Callback thread-safety**: callbacks invoked from an unexpected thread or
  event loop; re-entrancy into the scheduling code.
- **Shutdown**: concurrent `Close` vs in-flight work; double close; waiters
  never signaled.

## Per-language translation

| Language | High-signal checks |
|---|---|
| Go | goroutine leak (blocking send with no reader), unpropagated `context.Context`, `defer` inside loops, concurrent map writes, copied mutexes, `WaitGroup` misuse, `time.After` in loops |
| Rust | `unwrap`/`expect` in async paths, `std::sync` primitives blocking the async runtime, missing `Send`/`Sync` bounds, poisoned `Mutex` handling, blocking I/O in async tasks |
| Java | synchronization on mutable fields, shared non-thread-safe collections, unchecked exceptional completion of `CompletableFuture`, `ThreadLocal` leaks in pooled executors |
| C# | `async void`, `ConfigureAwait` mismatches, unobserved `CancellationToken`, holding `lock` across `await`, shared `IDisposable` lifetime |
| C++ | data races on members without synchronization, detached threads, use-after-move, destructor ordering with in-flight callbacks |
| Python / TypeScript | unhandled promise rejections, swallowed asyncio cancellation, shared mutable state in event-loop callbacks, stale closures over mutable state |

For every async boundary or shared-state change in the diff, attempt at least
one concrete interleaving scenario (concurrent call, cancellation mid-flight,
or shutdown race) and record the outcome.
