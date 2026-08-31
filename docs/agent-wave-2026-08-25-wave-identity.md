# Collision-free wave identity

## Result

Wave notebooks now use a six-digit monotonic sequence scoped to the persisted
run directory. Two completed waves are therefore `000001` and `000002` even
when both start within the same wall-clock second or sequential `Swarm`
instances. Runtime and dry-run notebook names use the same identity contract.

The sequence is assigned only after bounded mission assembly passes the
post-assembly STOP guard and yields at least one job. If shutdown wins the next
race and no dispatch notebook is created, mission and identity state roll back.
An empty wave also consumes no identity. Existing six-digit legacy wave suffixes
remain readable by `swarm status` and seed a reconstructed runner's next value.
The six-digit sequence fails closed after `999999`. Concurrent `Swarm`
instances sharing one run directory are outside this contract.

## Evidence and boundary

A deterministic two-wave echo regression requires ten notebooks, two status
waves of five agents, five dispatches and retries per wave, and zero failures,
malformed records, or contract violations. Focused regressions also cover two
dry-run waves, an empty wave, reconstruction against one run directory, and a
shutdown injected immediately before the first runtime dispatch.

Classification: **INCREMENTAL / EMPIRICAL**. This fixes local identity and
accounting; it does not establish provider stability or eager per-agent refill.
