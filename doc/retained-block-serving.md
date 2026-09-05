# Serving a retained fork from a pruned node

`-serveretainedhistoricalblocks=1` allows explicit full-block/witness `GETDATA`
for active-chain bodies that are still on disk, including bodies more than
288 blocks behind the tip. Missing bodies are not restored. The node continues
to advertise `NODE_NETWORK_LIMITED`.

On a local signer with pending archive requests, ordinary peers can process
bounded post-handshake controls, `getheaders`, and one explicit block request
per visit. This does not grant authority privileges or change block validation.

Example serving-node settings:

```ini
serveretainedhistoricalblocks=1
prune=50000
maxconnections=125
maxoutboundfullrelay=12
maxoutboundblockrelay=4
maxaddnodeconnections=12
```

Increasing the prune target retains more data going forward; it does not
require a reindex or deleting the existing chain. The example reserves 108
inbound slots, 12 full-relay and 4 block-relay steady outbound slots plus one
temporary safety slot; up to 12 persistent addnodes are counted separately.

A stock peer still avoids automatically requesting older bodies from a
LIMITED-only source. After learning the alternative headers, the receiving
operator can call `getblockfrompeer <blockhash> <peerid>` for the missing prefix
in ancestor-first order. `{}` means scheduled; verify `getblock <blockhash>`
succeeds before proceeding. Use the alternative branch hashes, not the
receiver's active-chain `getblockhash(height)`. Confirm the receiver's final
tip hash after validation; serving bytes alone does not prove a reorganization.
