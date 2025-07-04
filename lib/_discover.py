#!/usr/bin/env python3
"""
Discover Uvicorn servers publishing a /health endpoint on port 10000
across every IPv4 subnet the current machine is attached to.

Dependencies:
    pip install netifaces aiohttp
"""

from __future__ import annotations

import asyncio as _asyncio
import ipaddress as _ipaddress
import contextlib as _contextlib
import socket as _socket
from typing import Final, Iterable

import aiohttp as _aiohttp
import netifaces as  _netifaces


PORT: Final[int] = 10000
HEALTH: Final[str] = "/fs/health/"
TIMEOUT_S: Final[float] = 0.3
MAX_CONNS: Final[int] = 256


async def _reverse_lookup(ip: str) -> str | None:
    try:
        hostname, _ = await _asyncio.get_running_loop().getnameinfo((ip, 0), flags=0)
        return hostname
    except _socket.gaierror as e:
        print("⚠️ Reverse lookup failed:", str(e), flush=True)
        return None


async def _is_healthy(
    ip: str,
    *,
    session: _aiohttp.ClientSession
) -> bool:
    url: str = f"http://{ip}:{PORT}{HEALTH}"
    # print("⛑️ Checking server health:", str(url), flush=True)

    try:
        async with session.get(url, timeout=_aiohttp.ClientTimeout(TIMEOUT_S)) as resp:
            return resp.status == 200

    except (_aiohttp.ClientError, _asyncio.TimeoutError):
        return False


def _local_ipv4_networks() -> set[_ipaddress.IPv4Network]:
    nets: set[_ipaddress.IPv4Network] = set()

    for iface in _netifaces.interfaces():
        with _contextlib.suppress(KeyError, ValueError):
            info = _netifaces.ifaddresses(iface)[_netifaces.AF_INET][0]
            ip   = _ipaddress.IPv4Address(info["addr"])
            mask = _ipaddress.IPv4Address(info["netmask"])

            if (
                ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_unspecified
                or not ip.is_private
            ):
                continue

            nets.add(_ipaddress.IPv4Network(f"{ip}/{mask}", strict=False))

    return nets


async def _scan_network(
    network: _ipaddress.IPv4Network,
    *,
    session: _aiohttp.ClientSession,
    semaphore: _asyncio.Semaphore,
    hits: set[str],
) -> None:
    print("👀 Scanning network:", str(network), flush=True)

    async def probe(ip: _ipaddress.IPv4Address) -> None:
        async with semaphore:
            if await _is_healthy(str(ip), session=session):
                hostname = await _reverse_lookup(str(ip))
                print("🟢 File-system server discovered:", f"{str(ip)} -> {hostname}", flush=True)
                hits.add(hostname or str(ip))

    tasks: Iterable[_asyncio.Task[None]] = (
        _asyncio.create_task(probe(ip)) for ip in network.hosts()
    )
    await _asyncio.gather(*tasks)


async def _discover() -> set[str]:
    subnets: set[_ipaddress.IPv4Network] = _local_ipv4_networks()
    
    if not subnets:
        print("❌ No File system servers detected.", flush=True)
        return set()
    else:
        print("🔎 Found", len(subnets), "subnets to scan.", flush=True)

    found: set[str] = set()
    semaphore = _asyncio.Semaphore(MAX_CONNS)

    async with _aiohttp.ClientSession() as session:
        await _asyncio.gather(
            *(_scan_network(net, session=session, semaphore=semaphore, hits=found)
              for net in subnets)
        )

    return found


def discover() -> set[str]:
    ips: set[str] = _asyncio.run(_discover())

    if not ips:
        print("🔴 No File-system servers discovered.", flush=True)
    
    return ips
