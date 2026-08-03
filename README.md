# namescheck

Finds startup names whose `.com` **and** `.ai` are both available, from a
list of 10k-100k candidate names.

## Why

Picking a good startup name is hard. Checking if a name's domains are
available is tedious: search `.com`, search `.ai`, write them down, repeat
100 times. This tool automates it - feed it 10k names, get back the ones
where both domains are free, ranked by how they sound. No more manual
checking, no more false hope on half-available names.

## Usage

```bash
pip install -r requirements.txt
python scanner.py
```

Input: `startup_names.txt` (one name per line). Output: `available_both.txt`,
written to as matches are found - no need to wait for the scan to finish.

Options (all optional, defaults match the files above):

```bash
python scanner.py \
  --input startup_names.txt \
  --output available_both.txt \
  --concurrency 100 \
  --timeout 10 \
  --max-retries 4
```

## How it works

For each name: check `.com` via RDAP. If taken, stop - never touches `.ai`
for that name. If free, check `.ai`. If both are free, append to
`available_both.txt` immediately. This is gated per-name (not "check all
.com, then all .ai"), so a name that loses on `.com` costs exactly one
request, not two.

Concurrency is bounded by a semaphore (`--concurrency`, default 100), on top
of a single `aiohttp.ClientSession` with a pooled, keep-alive connector -
one TCP/TLS handshake reused across many requests instead of one per lookup.

Transient failures (429, 5xx, timeouts) retry with exponential backoff
(`--max-retries`, default 4). A name that still fails after retries is
logged to `startup_names.errors` (tab-separated: name, tld, status) instead
of being silently dropped or wrongly counted as available.

**Resume**: every processed name (regardless of outcome) is appended to
`startup_names.progress`. Re-running the same command skips names already in
that file, so `Ctrl+C` or a crash loses at most the in-flight batch, not the
whole run. Delete `startup_names.progress` to start fresh.

**Ctrl+C**: cancels in-flight requests, prints a summary, exits cleanly.
Already-written matches and progress are safe on disk.

## Networking / providers

Availability is checked via RDAP (no HTML scraping):

- `.com` / `.net`: `rdap.verisign.com` (the registry's own RDAP server -
  authoritative, handles bulk queries well)
- `.ai`: `rdap.org/domain/{domain}` - IANA's RDAP bootstrap proxy. The
  registry's own host, `rdap.nic.ai`, doesn't resolve at all (checked
  2026-07-31 - DNS failure, not a rate limit), so this uses the bootstrap
  redirector instead, which is still real RDAP, not scraping. Cloudflare in
  front of the actual .ai RDAP server 403s requests with aiohttp's default
  User-Agent, so the session sends a browser-like one (see `run()` in
  `scanner.py`) - without it every `.ai` lookup gets misclassified as taken.

`HTTP 404` = available, `HTTP 200` = taken. This is configured in
`Config.rdap_endpoints` in `scanner.py` - a plain `dict[tld] -> URL
template`. To point a TLD at a different RDAP server or a registrar's bulk
availability API, change that one line; nothing else in the pipeline needs
to change as long as the response still distinguishes "not found" from
"found" via HTTP status. (A registrar API with a different response shape -
e.g. JSON body instead of status code - would also need a small change to
`classify_status`/`check_domain`.)

## Self-check

```bash
python test_scanner.py
```

Checks the RDAP status -> availability mapping (the one piece of branching
logic worth pinning down) without hitting the network.

## Files

- `scanner.py` - the tool
- `requirements.txt` - `aiohttp`, `tqdm`
- `test_scanner.py` - self-check
- `startup_names.progress`, `*.errors` - generated at runtime, safe to delete to reset
