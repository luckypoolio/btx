#!/usr/bin/env python3
# Copyright (c) 2026 The BTX developers
# Distributed under the MIT software license, see the accompanying file COPYING.
"""A stock requester explicitly downloads retained bodies beyond LIMITED range."""
from io import BytesIO

from test_framework.authproxy import JSONRPCException
from test_framework.messages import CBlockHeader, CInv, MSG_BLOCK, MSG_WITNESS_FLAG, NODE_NETWORK, NODE_NETWORK_LIMITED, msg_getdata, msg_headers
from test_framework.p2p import P2PInterface
from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import assert_equal, try_rpc


class RetainedBlockServingTest(BitcoinTestFramework):
    def set_test_params(self):
        self.num_nodes = 2
        self.setup_clean_chain = True
        self.noban_tx_relay = False
        # Block-serving policy is independent of the expensive regtest proof
        # transition. Both nodes still verify the same pre-transition blocks.
        proof_args = ["-regtestmatmulv4height=2147483647",
                      "-regtestrcheight=2147483647",
                      "-regtestrccoupledheight=2147483647"]
        self.extra_args = [["-prune=550", "-maxconnections=125",
                            "-maxoutboundfullrelay=12", "-maxoutboundblockrelay=4",
                            "-maxaddnodeconnections=12", *proof_args], proof_args]

    def setup_network(self):
        self.setup_nodes()

    def run_test(self):
        server, receiver = self.nodes
        blocks = self.generate(server, 292, sync_fun=self.no_op)
        oldest = blocks[0]
        request = msg_getdata([CInv(MSG_BLOCK | MSG_WITNESS_FLAG, int(oldest, 16))])
        peer = server.add_p2p_connection(P2PInterface())
        peer.send_message(request)
        peer.wait_for_disconnect(timeout=10)
        server.disconnect_p2ps()

        self.restart_node(0, self.extra_args[0] + ["-serveretainedhistoricalblocks=1"])
        services = int(server.getnetworkinfo()["localservices"], 16)
        assert services & NODE_NETWORK_LIMITED
        assert not services & NODE_NETWORK
        peer = server.add_p2p_connection(P2PInterface())
        peer.send_message(request)
        peer.wait_for_block(int(oldest, 16), timeout=10)
        peer.sync_with_ping()
        server.disconnect_p2ps()
        self.log.info("Received the retained witness block 291 blocks behind the tip")

        # Supply the alternate header chain explicitly to isolate body download
        # from automatic LIMITED peer selection. Every body below still travels
        # over P2P via the stock getblockfrompeer RPC and is validated by receiver.
        headers = []
        for block_hash in blocks:
            header = CBlockHeader()
            header.deserialize(BytesIO(bytes.fromhex(server.getblockheader(block_hash, False))))
            headers.append(header)
        header_peer = receiver.add_p2p_connection(P2PInterface())
        header_peer.send_message(msg_headers(headers))
        self.wait_until(lambda: receiver.getblockchaininfo()['headers'] == 292, timeout=30)
        receiver.disconnect_p2ps()
        self.connect_nodes(1, 0)
        peer_id = receiver.getpeerinfo()[0]["id"]
        for block_hash in blocks:
            if not try_rpc(-1, "Block not available (not fully downloaded)", receiver.getblock, block_hash):
                continue
            try:
                receiver.getblockfrompeer(block_hash, peer_id)
            except JSONRPCException as error:
                # Automatic near-tip fetching may win the race after the
                # historical prefix brings this peer inside the normal window.
                if error.error['message'] not in ('Block already downloaded', 'Already requested from this peer'):
                    raise
            self.wait_until(lambda: not try_rpc(-1, "Block not available (not fully downloaded)", receiver.getblock, block_hash), timeout=30)
        self.sync_blocks([server, receiver])
        assert_equal(receiver.getbestblockhash(), blocks[-1])
        self.log.info("Stock requester downloaded and validated all 292 block bodies")


if __name__ == "__main__":
    RetainedBlockServingTest(__file__).main()
