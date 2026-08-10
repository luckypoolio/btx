# Snapshot foreground-priority hotfix seal

This hotfix carries the reviewed v0.33.2 Profile-1 CUDA/Metal production
digest forward to source revision
`26c41c4746734f738c15b1f84562bf17427c0b3f` with build fingerprint
`1100ed1d8f319dae4e7b9011a03847898994a1af20c6dea8e24dec70e0a27e0a`.

The build-relevant delta from release revision
`b4671ec28bb24e2fcbdd8252576119d54fd95238` is limited to:

- `src/net_processing.cpp`
- `src/net_processing.h`
- `src/test/matmul_rc_admission_tests.cpp`
- `src/test/net_peer_connection_tests.cpp`

No MatMul, CUDA, consensus, production-canary, or evidence-tool source changed.
The expected production digest and its independently reproduced corpus remain
those in `multi-gpu-profile1-goldens-cuda-metal-2026-08-04-v0332-final`.

The networking changes reserve download capacity for the active snapshot tip,
serialize resource-commitment-family tip downloads at `active_height + 1`, and
put a resource-commitment body on an independent budget cooldown when
verification work cannot reserve its per-peer or global token bucket. Valid
admission sidecars cannot clear that budget state. This prevents historical or
out-of-order blocks from consuming the scarce verification budget and
suppresses immediate body-request retry floods.

Deployment requires all of the following to pass before the release symlink is
switched:

1. The `net_peer_connection_tests` unit suite.
2. A clean production build with the revision and fingerprint above embedded.
3. The startup production canary on the target SM120 device, including an exact
   manifest match, zero CPU calls/fallbacks, and the reviewed expected digest.
