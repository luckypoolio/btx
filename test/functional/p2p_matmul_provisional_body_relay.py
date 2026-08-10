#!/usr/bin/env python3
# Copyright (c) 2026 The BTX developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""Prevent provisional RC relay and catch-up from stranding block bodies.

Topology is 0--1--2.  Node 1 provisionally relays a paid direct-tip RC header
to high-bandwidth peer 2 while its own ExactReplay is still running.  Node 2
may request the body before node 1 has accepted it.  Once node 1 authenticates
the block it must push the full payload-bearing block, rather than only repeat
the already-known header and leave node 2's first request stuck until timeout.
The test runs both payload-bearing full-block relay and ordinary compact-block
relay, and sends more blocks than the unknown-ticket per-netgroup allowance in
each mode to prove outbound ordering does not misclassify honest tickets as
unknown. It then reconnects a node several blocks behind and proves headers
direct-fetch keeps exactly one requested body in the single-flight RC lane;
descendant bodies must not arrive untracked and enter the retry cooldown.
"""

from contextlib import ExitStack

from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import assert_equal


V4_HEIGHT = 6
RC_HEIGHT = 9


class MatMulProvisionalBodyRelayTest(BitcoinTestFramework):
    def add_options(self, parser):
        parser.add_argument(
            "--product-payload",
            action="store_true",
            help="exercise payload-bearing full-block relay instead of compact relay",
        )

    def set_test_params(self):
        self.num_nodes = 3
        self.setup_clean_chain = True
        product_digest_height = 2 if self.options.product_payload else 2_147_483_647
        common = [
            "-test=matmulstrict",
            "-test=matmuldgw",
            "-matmulasyncverify=1",
            "-matmulrcprovisionalrelay=1",
            "-debug=net",
            "-regtestmatmulbindingheight=2",
            f"-regtestmatmulproductdigestheight={product_digest_height}",
            "-regtestmatmulrequireproductpayload=0",
            f"-regtestmatmulv4height={V4_HEIGHT}",
            "-regtestmatmulv4dimension=128",
            f"-regtestbmx4cheight={V4_HEIGHT}",
            f"-regtestdrltheight={V4_HEIGHT}",
            "-regtestmatmulltsealaspow=0",
            f"-regtestrcheight={RC_HEIGHT}",
            "-regtestrccoupledheight=12",
            "-regtestrctoydims=1",
            "-regtestrccoupledtoydims=1",
        ]
        self.extra_args = [common] * self.num_nodes

    def run_test(self):
        node0, node1, node2 = self.nodes

        # Establish high-bandwidth compact-block relay state before RC. The
        # product-payload variant cannot use compact encoding. The default
        # variant deliberately exercises the ordinary compact-body branch.
        self.generate(node0, RC_HEIGHT - 1)
        self.wait_until(
            lambda: all(node.getblockcount() == RC_HEIGHT - 1 for node in self.nodes),
            timeout=120,
        )

        # Ten rapid RC blocks exceed the unknown-ticket quarantine allowance.
        # A sender that puts RCADMIT before the corresponding header strands
        # the later blocks when those otherwise honest sidecars are dropped.
        rc_burst = 10
        expected_relay = ["matmul: provisionally relayed paid header"]
        if self.options.product_payload:
            expected_relay.append("sending full block")
        else:
            # Header-first paid relay may cause the downstream peer to request
            # the compact body before this node's ExactReplay completes. Once
            # validation finishes, prove the normal compact-body send path
            # answers that request; a second provisional compact push is not
            # required for correctness.
            expected_relay.append("sending cmpctblock")
        with ExitStack() as logs:
            logs.enter_context(node1.assert_debug_log(
                expected_msgs=expected_relay,
                unexpected_msgs=["dropping unknown rcadmit"],
                timeout=120,
            ))
            logs.enter_context(node2.assert_debug_log(
                expected_msgs=[],
                unexpected_msgs=["dropping unknown rcadmit"],
                timeout=120,
            ))
            self.generate(node0, rc_burst, sync_fun=self.no_op)
            expected = node0.getbestblockhash()
            self.wait_until(
                lambda: node2.getblockcount() == RC_HEIGHT - 1 + rc_burst
                and node2.getbestblockhash() == expected,
                timeout=120,
            )

        assert_equal(node1.getbestblockhash(), expected)
        assert node0.getconnectioncount() > 0
        assert node1.getconnectioncount() > 0
        assert node2.getconnectioncount() > 0

        # Reproduce production catch-up: a peer reconnects after several RC
        # blocks and receives them in one headers response. Direct fetch must
        # request one body at a time, otherwise SendMessages drops the later
        # in-flight markers while their already-sent bodies are still arriving.
        self.disconnect_nodes(1, 2)
        catchup_burst = 6
        self.generate(node0, catchup_burst, sync_fun=self.no_op)
        self.wait_until(
            lambda: node1.getblockcount() == RC_HEIGHT - 1 + rc_burst + catchup_burst,
            timeout=120,
        )
        assert_equal(node2.getblockcount(), RC_HEIGHT - 1 + rc_burst)

        with node2.assert_debug_log(
            expected_msgs=[],
            unexpected_msgs=[
                "lower-priority block requests",
                "RC ExactReplay requires rcadmit",
            ],
            timeout=120,
        ):
            self.connect_nodes(1, 2)
            expected = node1.getbestblockhash()
            self.wait_until(
                lambda: node2.getblockcount() == node1.getblockcount()
                and node2.getbestblockhash() == expected,
                timeout=120,
            )


if __name__ == "__main__":
    MatMulProvisionalBodyRelayTest(__file__).main()
