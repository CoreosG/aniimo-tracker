# Self-hosting the party relay

The relay has no map images, OCR, database or ledger. It keeps only ephemeral
party membership, layout evidence and player coordinates in RAM. It uses one
async process; do not run multiple independent replicas behind a load balancer
without shared room routing. Restarting the relay expires all invite codes.

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
.venv/bin/python party_server.py --host 127.0.0.1 --port 8787
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
  layout changes send full state. Each recipient has one replaceable pending
  update; a slow reader is disconnected rather than delaying other rooms.
- No WebSocket compression, image processing, screenshot uploads or persistent
  player records. Stale positions fade and disappear after 30 seconds.
- Idle WebSocket connections have ping timeouts; empty rooms disappear after
  the reconnect grace period. Invite codes and rooms are not written to disk.

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

## Shared-run rules

The creator is the host. The host can press **New shared run**; starting a new
tracked/map-only run as the host also resets party navigation. Other members
do not reset everyone when they start or save their own run. After finishing a
run, a member waits for the host's next shared run before adopting another map.

A single unambiguous full-map result supplies local layout evidence. Its score
uses the weaker portal match, reduced for covered portals. A strictly higher
score replaces shared evidence. Scores are client-reported comparisons, not
probabilities or anti-cheat attestations. Receiving a layout does not generate
new evidence. New runs and corrected layouts invalidate old position updates.
