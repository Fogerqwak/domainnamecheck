#!/usr/bin/env python3
"""Async scanner that finds startup names with both .com and .ai available.

Pipeline per name: check .com via RDAP -> if taken, stop -> if free, check
.ai -> if both free, append to the output file immediately. Streams output,
never buffers all results in memory, and resumes from where it left off.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import enum
import random
import signal
import time
from pathlib import Path

import aiohttp
from tqdm import tqdm


@dataclasses.dataclass(frozen=True)
class Config:
    input_file: Path = Path("startup_names.txt")
    output_file: Path = Path("available_both.txt")
    progress_file: Path = Path("startup_names.progress")
    errors_file: Path = Path("startup_names.errors")
    tlds: tuple[str, str] = ("com", "ai")
    concurrency: int = 100
    timeout: float = 10.0
    max_retries: int = 4
    backoff_base: float = 0.5
    backoff_max: float = 20.0

    # RDAP endpoint per TLD, {domain} is replaced with "label.tld". Swap a
    # value here to point at a different RDAP server or registrar API -
    # nothing else in the pipeline needs to change as long as the response
    # still signals availability via HTTP 404 (free) / 200 (taken).
    rdap_endpoints: dict[str, str] = dataclasses.field(
        default_factory=lambda: {
            "com": "https://rdap.verisign.com/com/v1/domain/{domain}",
            "net": "https://rdap.verisign.com/net/v1/domain/{domain}",
            # rdap.nic.ai does not resolve (dead host, verified 2026-07-31) -
            # use IANA's RDAP bootstrap proxy instead, which redirects to
            # whichever RDAP server the .ai registry actually runs today.
            "ai": "https://rdap.org/domain/{domain}",
        }
    )


class DomainStatus(enum.Enum):
    AVAILABLE = "available"
    TAKEN = "taken"
    UNKNOWN = "unknown"  # exhausted retries / persistent error


def classify_status(http_status: int) -> DomainStatus | None:
    """Map an RDAP HTTP status to a DomainStatus, or None to trigger a retry."""
    if http_status == 404:
        return DomainStatus.AVAILABLE
    if http_status == 200:
        return DomainStatus.TAKEN
    if http_status == 429 or http_status >= 500:
        return None  # retryable
    return DomainStatus.TAKEN  # unexpected 4xx: be conservative, assume taken


@dataclasses.dataclass
class Stats:
    processed: int = 0
    available_com: int = 0
    checked_ai: int = 0
    available_both: int = 0
    retries: int = 0
    errors: int = 0
    active: int = 0
    total_latency: float = 0.0
    request_count: int = 0

    @property
    def avg_latency_ms(self) -> float:
        return (self.total_latency / self.request_count * 1000) if self.request_count else 0.0


async def check_domain(
    session: aiohttp.ClientSession, cfg: Config, stats: Stats, label: str, tld: str
) -> DomainStatus:
    url = cfg.rdap_endpoints[tld].format(domain=f"{label}.{tld}")
    delay = cfg.backoff_base

    for attempt in range(cfg.max_retries + 1):
        start = time.monotonic()
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=cfg.timeout)) as resp:
                stats.total_latency += time.monotonic() - start
                stats.request_count += 1
                status = classify_status(resp.status)
                if status is not None:
                    return status
                raise aiohttp.ClientError(f"HTTP {resp.status}")
        except (aiohttp.ClientError, asyncio.TimeoutError):
            if attempt == cfg.max_retries:
                stats.errors += 1
                return DomainStatus.UNKNOWN
            stats.retries += 1
            await asyncio.sleep(min(delay, cfg.backoff_max) + random.uniform(0, delay * 0.1))
            delay *= 2

    return DomainStatus.UNKNOWN


async def process_name(
    session: aiohttp.ClientSession,
    cfg: Config,
    stats: Stats,
    sem: asyncio.Semaphore,
    name: str,
    out_fh,
    err_fh,
    progress_fh,
    bar: tqdm,
    start_time: float,
) -> None:
    com_tld, ai_tld = cfg.tlds
    async with sem:
        stats.active += 1
        try:
            com_status = await check_domain(session, cfg, stats, name, com_tld)
            if com_status is DomainStatus.AVAILABLE:
                stats.available_com += 1
                ai_status = await check_domain(session, cfg, stats, name, ai_tld)
                stats.checked_ai += 1
                if ai_status is DomainStatus.AVAILABLE:
                    stats.available_both += 1
                    out_fh.write(name + "\n")
                    out_fh.flush()
                elif ai_status is DomainStatus.UNKNOWN:
                    err_fh.write(f"{name}\t.{ai_tld}\tunknown\n")
                    err_fh.flush()
            elif com_status is DomainStatus.UNKNOWN:
                err_fh.write(f"{name}\t.{com_tld}\tunknown\n")
                err_fh.flush()
        except asyncio.CancelledError:
            raise
        else:
            stats.processed += 1
            progress_fh.write(name + "\n")
            progress_fh.flush()
            bar.update(1)
            elapsed = time.monotonic() - start_time
            bar.set_postfix(
                {
                    "com_avail": stats.available_com,
                    "ai_checked": stats.checked_ai,
                    "both": stats.available_both,
                    "req/s": f"{stats.request_count / elapsed:.1f}" if elapsed else "0",
                    "retries": stats.retries,
                    "avg_ms": f"{stats.avg_latency_ms:.0f}",
                    "conc": stats.active,
                },
                refresh=False,
            )
        finally:
            stats.active -= 1


def load_names(cfg: Config) -> list[str]:
    with open(cfg.input_file) as f:
        return [line.strip().lower() for line in f if line.strip()]


def load_progress(cfg: Config) -> set[str]:
    if not cfg.progress_file.exists():
        return set()
    with open(cfg.progress_file) as f:
        return {line.strip() for line in f if line.strip()}


async def run(cfg: Config) -> None:
    names = load_names(cfg)
    done = load_progress(cfg)
    todo = [n for n in names if n not in done]
    if done:
        print(f"Resuming: {len(done)} names already processed, {len(todo)} remaining.")
    if not todo:
        print("Nothing to do - all names already processed.")
        return

    stats = Stats()
    sem = asyncio.Semaphore(cfg.concurrency)
    connector = aiohttp.TCPConnector(
        limit=cfg.concurrency, limit_per_host=cfg.concurrency, keepalive_timeout=30
    )
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(signal.SIGINT, stop_event.set)
    except NotImplementedError:
        signal.signal(signal.SIGINT, lambda *_: stop_event.set())

    async with aiohttp.ClientSession(
        connector=connector, headers={"Accept": "application/rdap+json"}
    ) as session:
        with open(cfg.output_file, "a", buffering=1) as out_fh, open(
            cfg.progress_file, "a", buffering=1
        ) as progress_fh, open(cfg.errors_file, "a", buffering=1) as err_fh:
            bar = tqdm(total=len(todo), unit="name", desc="Scanning")
            start_time = time.monotonic()

            tasks = [
                asyncio.create_task(
                    process_name(session, cfg, stats, sem, name, out_fh, err_fh, progress_fh, bar, start_time)
                )
                for name in todo
            ]

            async def watch_stop() -> None:
                await stop_event.wait()
                bar.write("\nCtrl+C received, finishing in-flight requests and exiting...")
                for t in tasks:
                    t.cancel()

            watcher = asyncio.create_task(watch_stop())
            await asyncio.gather(*tasks, return_exceptions=True)
            watcher.cancel()
            bar.close()

    print_summary(stats, interrupted=stop_event.is_set())


def print_summary(stats: Stats, interrupted: bool) -> None:
    print("=" * 60)
    print("Interrupted - progress saved, rerun to resume." if interrupted else "Scan complete.")
    print(f"Processed:        {stats.processed}")
    print(f"Available .com:   {stats.available_com}")
    print(f"Checked .ai:      {stats.checked_ai}")
    print(f"Available both:   {stats.available_both}")
    print(f"Retries:          {stats.retries}")
    print(f"Errors (unknown): {stats.errors}")
    print(f"Avg latency:      {stats.avg_latency_ms:.0f} ms")
    print("=" * 60)


def parse_args() -> Config:
    default = Config()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, default=default.input_file)
    p.add_argument("--output", type=Path, default=default.output_file)
    p.add_argument("--progress-file", type=Path, default=default.progress_file)
    p.add_argument("--errors-file", type=Path, default=default.errors_file)
    p.add_argument("--concurrency", type=int, default=default.concurrency)
    p.add_argument("--timeout", type=float, default=default.timeout)
    p.add_argument("--max-retries", type=int, default=default.max_retries)
    args = p.parse_args()
    return dataclasses.replace(
        default,
        input_file=args.input,
        output_file=args.output,
        progress_file=args.progress_file,
        errors_file=args.errors_file,
        concurrency=args.concurrency,
        timeout=args.timeout,
        max_retries=args.max_retries,
    )


def main() -> None:
    cfg = parse_args()
    try:
        asyncio.run(run(cfg))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
