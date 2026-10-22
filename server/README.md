# Self-hosting the party relay

The relay has no map images, OCR, database or ledger. Live party membership,
layout evidence and player coordinates stay in RAM, with an optional short-lived
restart checkpoint for membership and layout only. It uses one
async process; do not run multiple independent replicas behind a load balancer
without shared room routing. Without the checkpoint, restarting expires all codes.

## Docker

From the repository root:

```sh
docker compose -p eggheist-party -f server/compose.yml up -d --build
curl http://127.0.0.1:8787/health
```

The container runs as a non-root user with a read-only filesystem, bounded logs,
512 MiB of memory and 1.5 CPUs. Only port **8787 on loopback** is published.
Put a TLS reverse proxy in front of it. Example Caddy configuration:

```caddyfile
eggheist.example.com {
    reverse_proxy 127.0.0.1:8787 {
        header_up X-Real-IP {remote_host}
    }
}
```

Adapt `bind` to your host when another process owns other interfaces. If using
Cloudflare, point the proxied record at the origin and allow WebSockets. The
app's address is `wss://eggheist.example.com/party`, normally on port 443.
The unencrypted relay port does not need to be exposed to the internet.

In the app, open **Party → Custom / self-hosted server**, enter that address and
save your profile. Every party member must use the same server. The default
button selects `wss://eggheist.banneret.app/party`.

## Without Docker

Requires Python 3.11 or newer:

```sh
python -m venv .venv
.venv/bin/pip install -r server/requirements.txt
.venv/bin/python src/party_server.py --host 127.0.0.1 --port 8787
```

Use your service manager to supervise it. `--host 0.0.0.0` with `ws://` can be
used for a trusted LAN; public deployments should use TLS.

## Limits and capacity

- Three members per party, including reconnect reservations for 60 seconds.
- 8-character cryptographically random invite codes; each member also receives
  a private random reconnect token. Tokens never appear in party broadcasts or
  the saved profile. Treat invite codes as access to that party's locations.
- At most 1,000 rooms and 3,200 open connections by default. These are admission
  limits, not a guarantee that every deployment can sustain them.
- Three incoming updates per second per connection, with a small burst allowance.
  The desktop normally sends at most two per second. Frames are limited to 2 KiB.
- Position changes are batched every 250 ms into compact deltas. Membership and
  layout changes send full state; an idle party also receives a full snapshot
  every 15 seconds to repair a missed roster notification. Each recipient has one replaceable pending
  update; a slow reader is disconnected rather than delaying other rooms.
- No WebSocket compression, image processing, screenshot uploads or permanent
  player history. Stale positions fade and disappear after 30 seconds.
- Idle WebSocket connections have ping timeouts; empty rooms disappear after
  the reconnect grace period. Optional restart checkpoints expire quickly; see below.

Set `PARTY_MAX_ROOMS`, `PARTY_MAX_CONNECTIONS`, and `PARTY_PER_IP` in Compose to
adjust admission. The per-IP limit defaults to 30; increase it if many real
players share one public address. The relay trusts `X-Real-IP` only from a
loopback proxy; that proxy must overwrite the header as shown above.
Docker's example enables `PARTY_TRUST_PROXY=1` because Docker NAT changes the
transport peer address. Keep the port bound to loopback and the network private
when using this setting; do not enable it on a directly exposed listener.
For Cloudflare edges, the relay recognizes the
[published IP ranges](https://www.cloudflare.com/ips/) and uses
[`CF-Connecting-IP`](https://developers.cloudflare.com/fundamentals/reference/http-headers/#cf-connecting-ip)
only when the proxy's recorded peer is in those ranges. Direct visitors cannot
override their rate-limit identity with that header. Update the ranges if
Cloudflare changes them.

Run `python server/load_test.py --url ws://127.0.0.1:8787/party --players 300`
against a **separate test instance**, with its per-IP limit increased. The test
reports delivered updates, latency, throughput and disconnects. Measure the
proxy and internet path separately before increasing production limits.

## Diagnostics

`docker compose -p eggheist-party -f server/compose.yml logs --since 10m party`
shows JSON events from `party.relay`. `member_connected`, `member_disconnected`
and `reservation_expired` record membership changes. `roster_sent` confirms that
a changed roster was handed to a connection's WebSocket transport; it does not
prove the remote UI displayed it. `writer_failed` identifies a closed or slow
transport. Random diagnostic `room` and per-connection `link` IDs correlate these
events without exposing invite codes, member identities, names, tokens or IPs.
IDs are discarded on restart. No coordinates or screenshots are logged.

Once per minute, `health` summarizes room/connection counts and interval totals
for full snapshots, position deltas, coalesced full states, rejected messages
and writer failures. There are no per-position logs or stored player histories.
Compose rotates logs at two files of 5 MB each. Detailed diagnostics are not
exposed through the public health endpoint.

## Restart recovery cache

Compose enables `PARTY_CACHE_PATH=/data/party-cache.json` on a named volume owned
by the relay's non-root user. Without Docker, set this variable to a private
writable path, or omit it to keep the relay entirely in memory. Only one relay
process may use a cache; this does not enable replicas or load balancing.

The cache contains invite codes, names/colors, member IDs, shared layout/session
state and SHA-256 hashes of random reconnect tokens. It contains **no raw tokens,
coordinates, screenshots or financial data**. File permissions are owner-only.
Snapshots replace the old file atomically, off the event loop, at most once per
second after changes and every ten seconds while parties exist.

An online member's checkpoint expires after 60 seconds; offline members retain
their existing reconnect deadline. After a quick restart, the existing desktop
client reconnects with its original identity/code. Everyone initially appears
offline and positions must be observed again. Long outages expire the party.
Explicit Leave removes the reservation from the next checkpoint; an abrupt
crash can lose changes since the last completed write. This is a small recovery
cache, not a database of player history. Expired data is removed on the next
checkpoint while running; when stopped, expired file contents remain until the
relay starts again or the volume is removed. Corrupt/unreadable cache files are
reported without exposing their contents and do not prevent new parties.

The first deployment enabling this feature still resets existing in-memory
parties once. Future short relay restarts can recover the last checkpoint.

## Shared-run rules

The creator is the host and controls difficulty. Any member can press **New shared run**. Starting the next tracked run announces a shared session only after completing the current one; finishing an older ledger run and catching up does not reset newer navigation. New sessions clear positions and layout, even if the next layout repeats. A confirmed map may show an optional unfinished-run notice. Notices never modify saved runs.

A single unambiguous full-map result supplies local layout evidence. Its score
uses the weaker portal match, reduced for covered portals. A strictly higher
score replaces shared evidence. Scores are client-reported comparisons, not
probabilities or anti-cheat attestations. Receiving a layout does not generate
new evidence. New runs and corrected layouts invalidate old position updates.
