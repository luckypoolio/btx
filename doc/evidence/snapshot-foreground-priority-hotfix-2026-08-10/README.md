# Snapshot foreground-priority hotfix seal

This hotfix carries the reviewed v0.33.2 Profile-1 CUDA/Metal production
digest forward to source revision
`349346a175c5bddc95d9ea951b1da51dfb85a435` with build fingerprint
`3953bc418685a2f6f9eb2ea2b62816a889c13b610d2ee2cab0680df6e3fc2847`.

The build-relevant delta from release revision
`b4671ec28bb24e2fcbdd8252576119d54fd95238` is limited to:

- `src/net_processing.cpp`
- `src/net_processing.h`
- `src/test/net_peer_connection_tests.cpp`

No MatMul, CUDA, consensus, production-canary, or evidence-tool source changed.
The expected production digest and its independently reproduced corpus remain
those in `multi-gpu-profile1-goldens-cuda-metal-2026-08-04-v0332-final`.

Deployment requires all of the following to pass before the release symlink is
switched:

1. The `net_peer_connection_tests` unit suite.
2. A clean production build with the revision and fingerprint above embedded.
3. The startup production canary on the target SM120 device, including an exact
   manifest match, zero CPU calls/fallbacks, and the reviewed expected digest.

