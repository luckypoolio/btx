# Snapshot foreground-priority hotfix seal

This hotfix carries the reviewed v0.33.2 Profile-1 CUDA/Metal production
digest forward to source revision
`5ef8cf07289e047f3e5876a8cd57ae1959076074` with build fingerprint
`2144c8b23c25a6c49a039391f4a7a847d2751b4bdaa5e3d1054eff12da371f36`.

The build-relevant delta from release revision
`b4671ec28bb24e2fcbdd8252576119d54fd95238` is limited to:

- `src/net_processing.cpp`
- `src/net_processing.h`
- `src/test/net_peer_connection_tests.cpp`

No MatMul, CUDA, consensus, production-canary, or evidence-tool source changed.
The expected production digest and its independently reproduced corpus remain
those in `multi-gpu-profile1-goldens-cuda-metal-2026-08-04-v0332-final`.

The networking changes reserve download capacity for the active snapshot tip,
serialize resource-commitment-family tip downloads at `active_height + 1`, and
put a resource-commitment body on the existing cooldown when verification work
cannot reserve the global budget. This prevents historical or out-of-order
blocks from consuming the scarce verification budget and suppresses immediate
body-request retry floods.

Deployment requires all of the following to pass before the release symlink is
switched:

1. The `net_peer_connection_tests` unit suite.
2. A clean production build with the revision and fingerprint above embedded.
3. The startup production canary on the target SM120 device, including an exact
   manifest match, zero CPU calls/fallbacks, and the reviewed expected digest.
