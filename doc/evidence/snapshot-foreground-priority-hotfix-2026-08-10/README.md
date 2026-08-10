# Snapshot foreground-priority hotfix seal

This hotfix carries the reviewed v0.33.2 Profile-1 CUDA/Metal production
digest forward to source revision
`d61048cc2c0a3364801b687a1fb7af3d7a85b11a` with build fingerprint
`a70f4fb8e4c5d22df3274db11393457ff93b94ec5caccafc7464dd1f6acd9a1f`.

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
cannot clear the budget state. A started asynchronous replay counts as the one
global in-flight job, and spending or exhausting its 129-unit allowance closes
all RC body downloads for the matching 60-second budget window. This prevents
historical or out-of-order blocks from consuming the scarce verification
budget and suppresses immediate body-request retry floods.

Deployment requires all of the following to pass before the release symlink is
switched:

1. The `net_peer_connection_tests` unit suite.
2. A clean production build with the revision and fingerprint above embedded.
3. The startup production canary on the target SM120 device, including an exact
   manifest match, zero CPU calls/fallbacks, and the reviewed expected digest.
