#!/usr/bin/env python3
"""
Multi-Platform Bounty Hunter for AI Agents
===========================================
Auto-discovers paid bounties across TaskMarket, Speedbot, Algora, GitHub,
and other agent work platforms. Matches them to agent skills.

Usage:
    python bounty_hunter.py discover --skills security-audit,code-review
    python bounty_hunter.py monitor --interval 300
    python bounty_hunter.py platforms
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

PLATFORMS = {
    "taskmarket": {
        "name": "TaskMarket",
        "url": "https://taskmarket.dev/api/tasks?status=open",
        "type": "usdc",
        "chains": ["Base", "Arbitrum", "Solana"],
    },
    "speedbot": {
        "name": "Speedbot",
        "url": "https://speedbot.dev/api/exchange/services",
        "type": "usdc",
        "chains": ["Base"],
    },
    "algora": {
        "name": "Algora",
        "url": "https://api.github.com/search/issues?q=label:%22%F0%9F%92%8E+Bounty%22+state:open&per_page=50",
        "type": "usdc",
        "chains": ["Base"],
    },
    "github": {
        "name": "GitHub Bounties",
        "url": "https://api.github.com/search/issues?q=%22bounty%22+in:title+state:open&per_page=50",
        "type": "mixed",
        "chains": [],
    },
}

CACHE_DIR = Path.home() / ".bounty-hunter" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def fetch_json(url, headers=None, timeout=15):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "bounty-hunter/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        print(f"  [warn] {url}: {e}", file=sys.stderr)
        return None


def discover_taskmarket(skills=None):
    data = fetch_json(PLATFORMS["taskmarket"]["url"])
    if not data:
        return []
    tasks = data.get("tasks", data.get("data", []))
    bounties = []
    for t in tasks:
        reward = int(t.get("reward", 0)) / 1_000_006
        bounties.append({
            "platform": "TaskMarket",
            "id": t.get("id", ""),
            "title": (t.get("description", "") or "").split("\n")[0][:80],
            "reward_usdc": round(reward, 2),
            "mode": t.get("mode", "bounty"),
            "submissions": t.get("submissionCount", 0),
            "url": f"https://taskmarket.dev/tasks/{t.get('id', '')}",
            "competition": "low" if t.get("submissionCount", 0) < 10 else "high",
        })
    return bounties


def discover_algora(skills=None):
    headers = {"User-Agent": "bounty-hunter/1.0", "Accept": "application/vnd.github.v3+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    data = fetch_json(PLATFORMS["algora"]["url"], headers)
    if not data:
        return []
    bounties = []
    for item in data.get("items", []):
        repo = item.get("repository_url", "").split("/")[-2:]
        bounties.append({
            "platform": "Algora",
            "id": f"github:{'/'.join(repo)}#{item.get('number')}",
            "title": item.get("title", "")[:80],
            "reward_usdc": None,
            "mode": "pr",
            "submissions": item.get("comments", 0),
            "url": item.get("html_url", ""),
            "competition": "low" if item.get("comments", 0) < 5 else "high",
        })
    return bounties


def discover_github(skills=None):
    headers = {"User-Agent": "bounty-hunter/1.0", "Accept": "application/vnd.github.v3+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    data = fetch_json(PLATFORMS["github"]["url"], headers)
    if not data:
        return []
    bounties = []
    for item in data.get("items", []):
        repo = item.get("repository_url", "").split("/")[-2:]
        bounties.append({
            "platform": "GitHub",
            "id": f"github:{'/'.join(repo)}#{item.get('number')}",
            "title": item.get("title", "")[:80],
            "reward_usdc": None,
            "mode": "issue",
            "submissions": item.get("comments", 0),
            "url": item.get("html_url", ""),
            "competition": "low" if item.get("comments", 0) < 3 else "high",
        })
    return bounties


def discover_speedbot(skills=None):
    data = fetch_json(PLATFORMS["speedbot"]["url"])
    if not data:
        return []
    services = data.get("services", data.get("data", []))
    bounties = []
    for s in services:
        bounties.append({
            "platform": "Speedbot",
            "id": s.get("id", ""),
            "title": s.get("title", "")[:80],
            "reward_usdc": float(s.get("price_usdc", 0)),
            "mode": "service",
            "submissions": s.get("active_orders", 0),
            "url": f"https://speedbot.dev/products/{s.get('id', '')}",
            "competition": "low",
        })
    return bounties


ADAPTERS = {
    "taskmarket": discover_taskmarket,
    "algora": discover_algora,
    "github": discover_github,
    "speedbot": discover_speedbot,
}


def discover(skills=None, platforms=None, min_reward=0, low_competition_only=False):
    all_bounties = []
    platforms = platforms or list(ADAPTERS.keys())
    for pname in platforms:
        adapter = ADAPTERS.get(pname)
        if not adapter:
            continue
        print(f"  Scanning {PLATFORMS[pname]['name']}...", file=sys.stderr)
        try:
            bounties = adapter(skills)
            all_bounties.extend(bounties)
        except Exception as e:
            print(f"  [error] {pname}: {e}", file=sys.stderr)

    filtered = []
    for b in all_bounties:
        if min_reward and (b.get("reward_usdc") or 0) < min_reward:
            continue
        if low_competition_only and b.get("competition") != "low":
            continue
        filtered.append(b)

    filtered.sort(key=lambda x: x.get("reward_usdc") or 0, reverse=True)
    return filtered


def format_table(bounties):
    if not bounties:
        return "No bounties found."
    lines = []
    lines.append(f"{'Platform':<12} {'Reward':<10} {'Comp':<6} {'Subs':<6} {'Title'}")
    lines.append("-" * 90)
    for b in bounties:
        reward = f"${b['reward_usdc']:.2f}" if b.get("reward_usdc") else "?"
        comp = b.get("competition", "?")
        subs = b.get("submissions", 0)
        title = b.get("title", "")[:50]
        lines.append(f"{b['platform']:<12} {reward:<10} {comp:<6} {subs:<6} {title}")
    return "\n".join(lines)


def monitor(skills=None, interval=300, min_reward=0):
    print(f"Monitoring every {interval}s. Press Ctrl+C to stop.", file=sys.stderr)
    seen = set()
    while True:
        bounties = discover(skills, min_reward=min_reward, low_competition_only=True)
        new = [b for b in bounties if b["id"] not in seen]
        if new:
            print(f"\n{'='*60}")
            print(f"NEW BOUNTIES - {datetime.now(timezone.utc).isoformat()}")
            print(f"{'='*60}")
            print(format_table(new))
            for b in new:
                seen.add(b["id"])
        else:
            print(f"  [{datetime.now(timezone.utc).strftime('%H:%M:%S')}] No new bounties", file=sys.stderr)
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Multi-Platform Bounty Hunter")
    sub = parser.add_subparsers(dest="command")

    d = sub.add_parser("discover", help="Discover open bounties")
    d.add_argument("--skills", help="Comma-separated skills to match")
    d.add_argument("--platforms", help="Comma-separated platforms (default: all)")
    d.add_argument("--min-reward", type=float, default=0, help="Minimum reward in USDC")
    d.add_argument("--low-comp", action="store_true", help="Only low-competition bounties")

    m = sub.add_parser("monitor", help="Continuous monitoring")
    m.add_argument("--skills", help="Comma-separated skills to match")
    m.add_argument("--interval", type=int, default=300, help="Check interval in seconds")
    m.add_argument("--min-reward", type=float, default=0, help="Minimum reward in USDC")

    sub.add_parser("platforms", help="List supported platforms")

    args = parser.parse_args()

    if args.command == "discover":
        skills = args.skills.split(",") if args.skills else None
        platforms = args.platforms.split(",") if args.platforms else None
        bounties = discover(skills, platforms, args.min_reward, args.low_comp)
        print(format_table(bounties))
        print(f"\nTotal: {len(bounties)} bounties")

    elif args.command == "monitor":
        skills = args.skills.split(",") if args.skills else None
        monitor(skills, args.interval, args.min_reward)

    elif args.command == "platforms":
        print("Supported platforms:")
        for key, p in PLATFORMS.items():
            print(f"  {key:<12} {p['name']:<20} {p['type']:<8} chains: {', '.join(p['chains']) or 'N/A'}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
