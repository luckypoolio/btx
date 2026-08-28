# LuckyPool v0.34.4 full-block peer fix seal

This seal applies the reviewed v0.34.4 production goldens to LuckyPool's
network-only catch-up fix at commit `b84d9cde1e4d145a166274f93176dd42af324335`.

The build-relevant tree fingerprint is
`14a8d988b00d22e42ca4937c921fc6f642b2d64e9e5bdf07cf6cc6087f35baba`.
The change affects first-hole block-source selection in `net_processing.cpp`;
it does not alter MatMul inputs, kernels, transcript, or consensus rules.

The CUDA `sm_120` release remains fail-closed: startup must replay the official
v0.34.4 production canary and match digest
`b4777985d4f2621d0b9c119f4188ac7d80158fc92560ade96cc7a3fd8cfae953`
before advertising MatMul consensus validation or serving mining work.

Focused regressions:

- `peerman_tests/fresh_discovery_owner_yields_root_to_advertised_block_source`
- `peerman_tests/stale_tip_with_inflight_and_forty_peers_sends_getheaders`
- `peerman_tests/pindex_last_common_behind_tip_advances_and_does_not_rerequest`
- `peerman_tests/best_header_below_tip_rerequests_headers_and_converges`
