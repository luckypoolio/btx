# Snapshot foreground-priority hotfix seal

This hotfix carries the reviewed v0.33.2 Profile-1 CUDA/Metal production
digest forward to source revision
`47dc8a88959d3f0e2d2ec0ffadc6ab5e29df0352` with build fingerprint
`14b9dff7f2c364a929db0c02947ee6f38de6b02654b6807213863ff9f47b9d47`.

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
serialize resource-commitment-family downloads to the globally earliest useful
body selected from peer branch order, and put a resource-commitment body on an
independent budget cooldown when verification work cannot reserve its per-peer
or global token bucket. A competing branch may therefore begin at or below the
active height, while descendants remain serialized. Valid admission sidecars
cannot clear the budget state. This prevents historical or out-of-order blocks
from consuming the scarce verification budget and suppresses immediate
body-request retry floods.

Deployment requires all of the following to pass before the release symlink is
switched:

1. The `net_peer_connection_tests` unit suite.
2. A clean production build with the revision and fingerprint above embedded.
3. The startup production canary on the target SM120 device, including an exact
   manifest match, zero CPU calls/fallbacks, and the reviewed expected digest.
