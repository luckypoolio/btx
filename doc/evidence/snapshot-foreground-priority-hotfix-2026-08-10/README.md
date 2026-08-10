# Snapshot foreground-priority hotfix seal

This hotfix carries the reviewed v0.33.2 Profile-1 CUDA/Metal production
digest forward to source revision
`a8a96ddb53407a7f4fd6e72f7633bc1b487daadb` with build fingerprint
`fbfbba284e0505f1cdc0400128825ea828ecb598c46bd9050afc2a600813ef62`.

The build-relevant delta from release revision
`b4671ec28bb24e2fcbdd8252576119d54fd95238` is limited to:

- `src/init.cpp`
- `src/net_processing.cpp`
- `src/net_processing.h`
- `src/node/peerman_args.cpp`
- `src/pow.cpp`
- `src/pow.h`
- `src/test/matmul_rc_admission_tests.cpp`
- `src/test/matmul_v4_rc_tests.cpp`
- `src/test/net_peer_connection_tests.cpp`

No MatMul hashing, CUDA, consensus-validation, production-canary, or
evidence-tool source changed. The expected production digest and its
independently reproduced corpus remain those in
`multi-gpu-profile1-goldens-cuda-metal-2026-08-04-v0332-final`.

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
budget and suppresses immediate body-request retry floods. Requested or paid
work that directly extends the authenticated active tip toward a higher
consensus-capable peer may use a configurable, bounded four-job catch-up
allowance. Replay remains single-flight, while unsolicited and competing-branch
work retains the strict one-job allowance.

Deployment requires all of the following to pass before the release symlink is
switched:

1. The `net_peer_connection_tests`, `matmul_v4_rc_tests`, RC admission, and
   MatMul verify-worker unit suites.
2. A clean production build with the revision and fingerprint above embedded.
3. The startup production canary on the target SM120 device, including an exact
   manifest match, zero CPU calls/fallbacks, and the reviewed expected digest.
