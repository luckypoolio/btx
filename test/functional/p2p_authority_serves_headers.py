#!/usr/bin/env python3
# Copyright (c) 2026 The BTX developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/license/mit/.
"""An authority-mode node (local signer) must serve reads to ANY peer.

Regression test for the 0.34.1 release blocker measured 2026-08-27 on the
BTX main network: a node with a local attestation signer dispatched inbound
messages only for peers advertising MATMUL_TRUSTED_MIRROR or
MATMUL_ATTESTATION_ARCHIVE. SkipMinerProcessMessagesDuringArchiveGetData
discarded its archive_getdata_pending argument, turning a "yield while an
archive fetch is pending" into an unconditional skip of every fully
handshaked non-archive peer, so plain MATMUL_CONSENSUS peers and peers with
no matmul service bits received ZERO header bytes (getpeerinfo:
recv.getheaders > 0, sent.headers == 0). A fresh community node could not
bootstrap, synced_headers stayed -1 network-wide, and the mining chain
guard blocked block production with insufficient_peer_consensus.

Serving headers or a requested retained body is a read: authority rules govern
which BODIES a node TRUSTS, never who may ask it questions. The second
regression keeps an archive GETDATA backlog pending while a plain peer asks for
headers and 280 historical blocks, so the signer dispatcher cannot pass merely
because the archive worker emptied an unrealistically small request first.
Valid ADDR and HEADERS ingestion messages precede these reads, reproducing the
queue-front starvation that a handshake-only synthetic client does not expose.

Asserts by received messages and getpeerinfo byte counters, never by
debug.log strings (LogDebug lines are invisible without -debug=net).
"""

import socket
import threading

from test_framework.messages import (
    CInv,
    MAX_INV_SIZE,
    MSG_BLOCK,
    MSG_WITNESS_FLAG,
    NODE_NETWORK,
    NODE_NETWORK_LIMITED,
    NODE_WITNESS,
    msg_addr,
    msg_getdata,
    msg_getaddr,
    msg_getheaders,
    msg_headers,
    msg_sendcmpct,
    msg_sendheaders,
)
from test_framework.p2p import NetworkThread, P2PInterface
from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import assert_equal, assert_greater_than
from test_framework.wallet_util import generate_keypair

CHAIN_HEIGHT = 570
HISTORICAL_BODY_COUNT = 280
BODY_REQUEST_WINDOW = 16
NODE_MATMUL_ATTESTATION_ARCHIVE = 1 << 31
ARCHIVE_BACKPRESSURE_BYTES = 64 * 1024 * 1024

INLINE_SIGNER_WARNING = (
    "Warning: -matmulattestationsignerkey exposes an online signing key "
    "through process/config surfaces; use a permission-restricted "
    "-matmulattestationsignerkeyfile."
)


class PauseableP2P(P2PInterface):
    def pause_reading(self):
        """Stop draining replies so the node retains a real GETDATA backlog."""
        paused = threading.Event()
        errors = []

        def pause():
            try:
                sock = self._transport.get_extra_info("socket")
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
                self._transport.pause_reading()
            except Exception as exc:
                errors.append(exc)
            finally:
                paused.set()

        NetworkThread.network_event_loop.call_soon_threadsafe(pause)
        assert paused.wait(timeout=5)
        if errors:
            raise errors[0]


class BodyReader(P2PInterface):
    def __init__(self):
        super().__init__()
        self.received_bodies = {}

    def on_block(self, message):
        message.block.calc_sha256()
        self.received_bodies[message.block.hash] = message.block


class AuthorityServesHeadersTest(BitcoinTestFramework):
    def set_test_params(self):
        self.num_nodes = 1
        self.setup_clean_chain = True
        signer_wif, signer_pub = generate_keypair(wif=True)
        # Configured exactly like the production Authority: consensus
        # validation plus a local attestation signing key.
        self.extra_args = [[
            "-matmulvalidation=consensus",
            f"-matmultrustedpubkey={signer_pub.hex()}",
            "-matmultrustedthreshold=1",
            f"-matmulattestationsignerkey={signer_wif}",
            "-matmulattestationserve=1",
            "-serveretainedhistoricalblocks=1",
            "-prune=550",
            "-maxsendbuffer=1",
            # This is a dispatch/serving test, not a GPU proof-transition test.
            "-regtestmatmulv4height=2147483647",
            "-regtestrcheight=2147483647",
            "-regtestrccoupledheight=2147483647",
        ]]

    @staticmethod
    def peer_address(peer):
        sockname = peer._transport.get_extra_info("socket").getsockname()
        return f"{sockname[0]}:{sockname[1]}"

    def peer_info(self, address):
        matches = [
            info for info in self.nodes[0].getpeerinfo()
            if info["addr"] == address
        ]
        assert_equal(len(matches), 1)
        return matches[0]

    def assert_headers_served(self, services, label):
        node = self.nodes[0]
        tip = int(node.getbestblockhash(), 16)
        genesis = int(node.getblockhash(0), 16)

        kwargs = {} if services is None else {"services": services}
        peer = node.add_p2p_connection(P2PInterface(), **kwargs)

        req = msg_getheaders()
        req.locator.vHave = [genesis]
        req.hashstop = 0
        peer.send_message(req)

        # A non-empty HEADERS message must arrive, ending at the tip.
        peer.wait_until(
            lambda: peer.last_message.get("headers") is not None
            and len(peer.last_message["headers"].headers) > 0,
            timeout=30,
        )
        headers = peer.last_message["headers"].headers
        assert_greater_than(len(headers), 0)
        assert_equal(headers[-1].rehash(), tip)
        assert_equal(len(headers), CHAIN_HEIGHT)

        # Cross-check with the same counters used to measure the live bug.
        info = node.getpeerinfo()[-1]
        assert_greater_than(
            info["bytesrecv_per_msg"].get("getheaders", 0), 0)
        assert_greater_than(
            info["bytessent_per_msg"].get("headers", 0), 0)

        self.log.info(
            "%s: served %d headers, sent.headers=%d bytes",
            label, len(headers), info["bytessent_per_msg"]["headers"])
        node.disconnect_p2ps()

    def assert_reads_served_while_archive_getdata_pending(self):
        node = self.nodes[0]
        tip_hex = node.getbestblockhash()
        tip = int(tip_hex, 16)
        genesis = int(node.getblockhash(0), 16)

        archive = node.add_p2p_connection(
            PauseableP2P(),
            services=(
                NODE_NETWORK
                | NODE_WITNESS
                | NODE_MATMUL_ATTESTATION_ARCHIVE
            ),
        )
        archive_address = self.peer_address(archive)
        reader = node.add_p2p_connection(
            BodyReader(), services=NODE_NETWORK | NODE_WITNESS)
        reader_address = self.peer_address(reader)

        # One maximal GETDATA is small enough for the receive limit, while its
        # repeated block replies are much larger than the paused socket and
        # 1 kB node send buffer. This keeps archive_getdata_pending true while
        # the ordinary peer is dispatched.
        block_size = len(bytes.fromhex(node.getblock(tip_hex, 0)))
        request_count = min(
            MAX_INV_SIZE,
            (ARCHIVE_BACKPRESSURE_BYTES + block_size - 1) // block_size,
        )
        archive.pause_reading()
        archive_getdata = msg_getdata()
        archive_getdata.inv = [
            CInv(MSG_BLOCK | MSG_WITNESS_FLAG, tip)
            for _ in range(request_count)
        ]
        archive.send_message(archive_getdata)

        self.wait_until(
            lambda: self.peer_info(archive_address)["bytessent_per_msg"].get("block", 0) > 0,
            timeout=30,
        )
        expected_archive_block_bytes = request_count * block_size
        assert self.peer_info(archive_address)["bytessent_per_msg"].get(
            "block", 0) < expected_archive_block_bytes

        reader.send_message(msg_sendheaders())
        reader.send_message(msg_sendcmpct())
        reader.send_message(msg_getaddr())
        # These valid ingestion messages are not public reads. They must not
        # head-of-line block following read requests when archive work stalls
        # normal message ingestion on a signer node.
        reader.send_message(msg_addr())
        reader.send_message(msg_headers())
        req = msg_getheaders()
        req.locator.vHave = [genesis]
        req.hashstop = 0
        reader.send_message(req)
        reader.wait_until(
            lambda: reader.last_message.get("headers") is not None
            and len(reader.last_message["headers"].headers) > 0,
            timeout=10,
        )
        assert_equal(reader.last_message["headers"].headers[-1].rehash(), tip)

        # Every requested body is outside NODE_NETWORK_LIMITED's guaranteed
        # window, but still physically retained. Separate singleton GETDATA
        # messages mirror a peer issuing getblockfrompeer for a missing branch.
        assert_greater_than(CHAIN_HEIGHT - HISTORICAL_BODY_COUNT, 288)
        hashes = [node.getblockhash(height)
                  for height in range(1, HISTORICAL_BODY_COUNT + 1)]
        expected_bodies = {block_hash: node.getblock(block_hash, 0)
                           for block_hash in hashes}
        for offset in range(0, len(hashes), BODY_REQUEST_WINDOW):
            batch = hashes[offset:offset + BODY_REQUEST_WINDOW]
            reader.send_message(msg_addr())
            reader.send_message(msg_headers())
            for block_hash in batch:
                reader.send_message(msg_getdata([
                    CInv(MSG_BLOCK | MSG_WITNESS_FLAG, int(block_hash, 16)),
                ]))
            reader.wait_until(
                lambda: all(block_hash in reader.received_bodies for block_hash in batch),
                timeout=10,
            )
            assert self.peer_info(archive_address)["bytessent_per_msg"].get(
                "block", 0) < expected_archive_block_bytes
        assert_equal(len(reader.received_bodies), HISTORICAL_BODY_COUNT)
        for block_hash in hashes:
            body = reader.received_bodies[block_hash]
            assert_greater_than(len(body.vtx), 0)
            assert_equal(body.calc_merkle_root(), body.hashMerkleRoot)
            assert_equal(body.serialize().hex(), expected_bodies[block_hash])

        reader_info = self.peer_info(reader_address)
        assert_greater_than(reader_info["bytesrecv_per_msg"].get("getheaders", 0), 0)
        assert_greater_than(reader_info["bytessent_per_msg"].get("headers", 0), 0)
        assert_greater_than(reader_info["bytesrecv_per_msg"].get("getdata", 0), 0)
        assert_greater_than(reader_info["bytessent_per_msg"].get("block", 0), 0)

        # The backpressured archive still has unsent requested bodies after
        # both replies. The reads therefore happened under the pending gate,
        # not just after the archive queue happened to drain.
        assert self.peer_info(archive_address)["bytessent_per_msg"].get(
            "block", 0) < expected_archive_block_bytes
        self.log.info(
            "served headers and all %d retained bodies (>288 deep) while %d archive block requests remained backpressured",
            HISTORICAL_BODY_COUNT,
            request_count,
        )
        node.disconnect_p2ps()

    def run_test(self):
        node = self.nodes[0]
        self.generate(node, CHAIN_HEIGHT)
        assert_equal(node.getmatmultrustedstatus()["local_signer"], True)
        services = int(node.getnetworkinfo()["localservices"], 16)
        assert services & NODE_NETWORK_LIMITED
        assert not services & NODE_NETWORK

        # An inbound peer with NO matmul service bits and NO permissions.
        self.assert_headers_served(
            NODE_NETWORK | NODE_WITNESS, "no-matmul-bits peer")
        # An inbound peer with only MATMUL_CONSENSUS (the framework
        # default services) and NO permissions.
        self.assert_headers_served(None, "consensus-only peer")
        self.assert_reads_served_while_archive_getdata_pending()

        self.stop_node(0, expected_stderr=INLINE_SIGNER_WARNING)


if __name__ == "__main__":
    AuthorityServesHeadersTest(__file__).main()
