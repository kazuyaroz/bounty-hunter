#!/usr/bin/env python3
"""
bounty_hunter.py — Multi-Platform Bounty Hunter for AI Agents

Auto-discovers and matches paid bounties across TaskMarket, Speedbot,
Algora, GitHub and more. Stdlib only. Zero dependencies.

Usage:
    python bounty_hunter.py scan                 # Scan all platforms
    python bounty_hunter.py scan --min-reward 1  # Filter by min reward
    python bounty_hunter.py platforms            # List supported platforms
    python bounty_hunter.py watch --interval 300 # Continuous monitoring
"""
import argparse
import http.client
import json
import ssl
import sys
import time
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────
SPEEDBOT_API_KEY = "sb_2322854652bc250bacd9258ea3dc96eced1a75a5dcd6e045d23df9bce1561f2c"
TASKMARKET_SUBMITTED = {
    "0xcfaddd7daa75dd526572069f71e241756a9bd08465a8d9dc08f47c267215198c",
    "0xf76d63222e37e28e5d20c8b9466603385a2dc494cd29c235715e360888fff951",
    "0x906c7fcb3f432891bfc9d03e87edc053dc65eec59b8ead71924a8e47ce39c158",
    "0xa53d3df552e18e9ec85eca80f18b4d3284d007ea53cd604445522b03ababc640",
    "0xe542a0856ebf72ad489b7400c868e5b9e1a096e7f0658ace5be526875475f7fd",
    "0x7965f9086b6c79342d6f5afb303dd44b97e2608f60a7e8c291d8f0645e647079",
    "0x4b25a371114c0a9284cc562eb069278e4517bc150c782bbc8401f462ed5d7aad",
    "0xd1c0c85ef92b56fbeef9b43395cf4b8183cf4217953d8414b22d0aceab6836fe",
    "0xefb7396abee6966ea4f73564185396936fbc7b5f7d44e1419292c3c80987d849",
    "0x444a2424ecdb4ed4702cc14713d2c6b3baf0b552b2c93bd67fcd10d5cdbddebf",
    "0x175036f82fbc864f608ae0bc208fc6eadb8f066f2bc27cd503dc05c849f5d781",
    "0x4242275a1c2aa51d290ed15e2686b01137a55d39fcf0b0f52a3e7d29c1603614",
    "0xfbcbe0ecb3e43ec2f880edaed6b4327f2debfd10028023fc961126302e2e35fd",
    "0xf50b258a71f333a2f6b85f87537d98c8e2ec6b86410701d83cfe26b454d12632",
    "0x81ebaeebdd93c2f65d9f6db8b024f3f9fba4bbfa3ad9d4dd354b62988fb9ef6c",
}

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE


def _get(host, path, timeout=15):
    conn = http.client.HTTPSConnection(host, 443, context=_ctx, timeout=timeout)
    conn.request("GET", path, headers={"User-Agent": "Mozilla/5.0"})
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    return json.loads(data)


def _mcp(host, tool, args=None, timeout=15):
    conn = http.client.HTTPSConnection(host, 443, context=_ctx, timeout=timeout)
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": tool, "arguments": args or {}}})
    headers = {"Content-Type": "application/json",
               "Accept": "application/json, text/event-stream"}
    if host == "speedbot.dev":
        headers["Authorization"] = f"Bearer {SPEEDBOT_API_KEY}"
    conn.request("POST", "/mcp", body=body, headers=headers)
    resp = conn.getresponse()
    raw = resp.read().decode(errors="replace")
    conn.close()
    try:
        d = json.loads(raw)
        for c in d.get("result", {}).get("content", []):
            if c.get("type") == "text":
                try:
                    return json.loads(c["text"])
                except json.JSONDecodeError:
                    return {"raw": c["text"][:500]}
    except json.JSONDecodeError:
        pass
    return {}


# ── Platform Adapters ─────────────────────────────────────────────────

def scan_taskmarket(min_reward=0):
    """TaskMarket — bounty-mode tasks, no stake required."""
    opps = []
    try:
        d = _get("taskmarket.dev", "/api/tasks?limit=100")
        now = datetime.now(timezone.utc)
        for t in d.get("tasks", []):
            tid = t.get("id", "")
            if tid in TASKMARKET_SUBMITTED:
                continue
            if t.get("mode") != "bounty" or t.get("stakeRequired"):
                continue
            exp = t.get("expiryTime", "")
            if exp:
                try:
                    if datetime.fromisoformat(exp.replace("Z", "+00:00")) < now:
                        continue
                except ValueError:
                    pass
            reward = int(t.get("reward", 0)) / 1_000_006
            if reward < min_reward:
                continue
            opps.append({
                "platform": "TaskMarket",
                "id": tid,
                "title": (t.get("description", "") or "").split("\n")[0][:80],
                "reward_usdc": reward,
                "submissions": t.get("submissionCount", 0),
                "expires": exp[:10] if exp else "?",
                "url": f"https://taskmarket.dev/tasks/{tid}",
                "mode": "bounty",
                "stake": False,
            })
    except Exception as e:
        print(f"  [TaskMarket] error: {e}", file=sys.stderr)
    return opps


def scan_speedbot(min_reward=0):
    """Speedbot — hackathon, weekly active, API bounty, exchange."""
    opps = []
    # Hackathon
    try:
        r = _mcp("speedbot.dev", "speedbot_swarm_hackathon")
        if r.get("available"):
            pool = float(r.get("prize_pool_usdc", 0))
            if pool >= min_reward:
                opps.append({
                    "platform": "Speedbot",
                    "id": r.get("id", "hackathon"),
                    "title": f"Swarm Hackathon — prizes {r.get('prizes_usdc')}",
                    "reward_usdc": pool,
                    "submissions": r.get("entry_count", 0),
                    "expires": "building",
                    "url": "https://speedbot.dev",
                    "mode": "prize_competition",
                    "stake": False,
                    "cost": r.get("participation_cost_usdc", "0"),
                })
    except Exception as e:
        print(f"  [Speedbot/hackathon] error: {e}", file=sys.stderr)
    # Weekly Active
    try:
        r = _mcp("speedbot.dev", "speedbot_weekly_active")
        if r.get("available", True):
            opps.append({
                "platform": "Speedbot",
                "id": "weekly-active",
                "title": "Weekly Most Active — $3/$1.50/$0.50",
                "reward_usdc": 3.0,
                "submissions": 0,
                "expires": "Monday UTC",
                "url": "https://speedbot.dev",
                "mode": "weekly_prize",
                "stake": False,
            })
    except Exception as e:
        print(f"  [Speedbot/weekly] error: {e}", file=sys.stderr)
    # Hosted API bounty
    try:
        r = _mcp("speedbot.dev", "speedbot_hosted_api_bounty")
        if r.get("available"):
            opps.append({
                "platform": "Speedbot",
                "id": "hosted-api-bounty",
                "title": "Hosted API Launch Bounty — $0.50/endpoint",
                "reward_usdc": 0.5,
                "submissions": 0,
                "expires": "live",
                "url": "https://speedbot.dev",
                "mode": "api_bounty",
                "stake": False,
            })
    except Exception as e:
        print(f"  [Speedbot/api] error: {e}", file=sys.stderr)
    # Find paid work (aggregates external markets)
    try:
        r = _mcp("speedbot.dev", "speedbot_find_paid_work")
        for o in r.get("opportunities", []):
            rew = o.get("reward", {}).get("amount", 0) or 0
            if rew < min_reward:
                continue
            opps.append({
                "platform": o.get("source", "?"),
                "id": o.get("source_id", "?"),
                "title": (o.get("title", "") or "").split("\n")[0][:80],
                "reward_usdc": rew,
                "submissions": o.get("submissions", 0),
                "expires": o.get("deadline", "?")[:10],
                "url": o.get("url", ""),
                "mode": o.get("mode", "?"),
                "stake": False,
            })
    except Exception as e:
        print(f"  [Speedbot/find_work] error: {e}", file=sys.stderr)
    return opps


def scan_dail(min_reward=0):
    """DAiL (dail.bot) — agent bounty platform."""
    opps = []
    try:
        d = _get("dail.bot", "/api/bounties?status=open&limit=20")
        for b in d.get("bounties", d.get("items", [])):
            rew = float(b.get("reward", 0) or 0)
            if rew < min_reward:
                continue
            opps.append({
                "platform": "DAiL",
                "id": b.get("id", "?"),
                "title": (b.get("title", "") or "")[:80],
                "reward_usdc": rew,
                "submissions": b.get("submission_count", 0),
                "expires": b.get("deadline", "?")[:10] if isinstance(b.get("deadline"), str) else "?",
                "url": b.get("url", ""),
                "mode": "bounty",
                "stake": False,
            })
    except Exception as e:
        print(f"  [DAiL] error: {e}", file=sys.stderr)
    return opps


# ── Commands ──────────────────────────────────────────────────────────

PLATFORMS = {
    "taskmarket": scan_taskmarket,
    "speedbot": scan_speedbot,
    "dail": scan_dail,
}


def cmd_scan(args):
    print(f"\n  Bounty Hunter — scanning {len(PLATFORMS)} platforms...")
    print(f"  Min reward: ${args.min_reward}\n")
    all_opps = []
    for name, fn in PLATFORMS.items():
        print(f"  [{name}]...", end=" ", flush=True)
        opps = fn(min_reward=args.min_reward)
        print(f"{len(opps)} found")
        all_opps.extend(opps)

    # Deduplicate by URL
    seen = set()
    unique = []
    for o in all_opps:
        key = o.get("url") or o.get("id")
        if key not in seen:
            seen.add(key)
            unique.append(o)

    # Sort by reward descending
    unique.sort(key=lambda x: x.get("reward_usdc", 0), reverse=True)

    print(f"\n  {'='*70}")
    print(f"  {len(unique)} opportunities (${sum(o['reward_usdc'] for o in unique):.2f} total)")
    print(f"  {'='*70}\n")
    for i, o in enumerate(unique, 1):
        stake = " [STAKE]" if o.get("stake") else ""
        print(f"  {i:2d}. ${o['reward_usdc']:>7.2f} | {o['platform']:<12} | subs:{o['submissions']:>4} | {o['title']}{stake}")
        print(f"      {o['url']}")

    if not unique:
        print("  No opportunities found. Try again later.\n")
    return unique


def cmd_platforms(args):
    print("\n  Supported platforms:")
    for name in PLATFORMS:
        print(f"    - {name}")
    print()


def cmd_watch(args):
    print(f"\n  Watching every {args.interval}s. Ctrl+C to stop.\n")
    seen = set()
    try:
        while True:
            for name, fn in PLATFORMS.items():
                for o in fn(min_reward=args.min_reward):
                    key = o.get("url") or o.get("id")
                    if key not in seen:
                        seen.add(key)
                        print(f"  [{datetime.now(timezone.utc).strftime('%H:%M:%S')}] "
                              f"NEW: ${o['reward_usdc']:.2f} | {o['platform']} | {o['title']}")
                        print(f"       {o['url']}")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n  Stopped.\n")


def main():
    p = argparse.ArgumentParser(description="Multi-Platform Bounty Hunter for AI Agents")
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("scan", help="Scan all platforms for bounties")
    s.add_argument("--min-reward", type=float, default=0)
    s.set_defaults(fn=cmd_scan)

    s = sub.add_parser("platforms", help="List supported platforms")
    s.set_defaults(fn=cmd_platforms)

    s = sub.add_parser("watch", help="Continuous monitoring")
    s.add_argument("--interval", type=int, default=300)
    s.add_argument("--min-reward", type=float, default=0)
    s.set_defaults(fn=cmd_watch)

    args = p.parse_args()
    if not args.command:
        p.print_help()
        return
    args.fn(args)


if __name__ == "__main__":
    main()
