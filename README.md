# Multi-Platform Bounty Hunter for AI Agents

Open-source CLI tool that auto-discovers paid bounties across TaskMarket, Speedbot, Algora, GitHub, and other agent work platforms. Matches them to agent skills and provides real-time monitoring.

## The Problem

AI agents waste hours manually checking dozens of bounty platforms for earning opportunities. Each platform has a different API, different data format, and different submission flow. There is no unified way to discover, filter, and track paid work across the agent economy.

## The Solution

`bounty_hunter.py` is a single-file Python CLI (zero dependencies) that:

- **Discovers** open bounties from 4+ platforms in one command
- **Filters** by reward amount and competition level
- **Matches** bounties to your declared skills
- **Monitors** continuously and alerts on new opportunities
- **Outputs** structured data for further processing

## Quick Start

```bash
# List supported platforms
python bounty_hunter.py platforms

# Discover all open bounties (low competition only)
python bounty_hunter.py discover --low-comp

# Filter by skills and minimum reward
python bounty_hunter.py discover --skills security-audit,code-review --min-reward 5

# Continuous monitoring (checks every 5 minutes)
python bounty_hunter.py monitor --interval 300 --min-reward 1
```

## Example Output

```
Platform     Reward     Comp   Subs   Title
------------------------------------------------------------------------------------------
Speedbot     $199.00    low    0      Verified Competitor & Pricing Report
Speedbot     $9.00      low    0      Startup credits finder
TaskMarket   $1.00      low    2      FlapJax paid task Q76
Algora       ?          low    1      Serial by default: safe execution first

Total: 27 bounties
```

## Supported Platforms

| Platform | Type | Chains | Notes |
|----------|------|--------|-------|
| TaskMarket | USDC | Base, Arbitrum, Solana | On-chain task marketplace |
| Speedbot | USDC | Base | Agent work network with x402 escrow |
| Algora | USDC | Base | GitHub-integrated bounties |
| GitHub | Mixed | - | Direct issue bounties |

## Adding a New Platform

Each platform has a simple adapter function. To add a new one:

```python
def discover_newplatform(skills=None):
    data = fetch_json("https://api.newplatform.com/bounties")
    if not data:
        return []
    bounties = []
    for item in data.get("items", []):
        bounties.append({
            "platform": "NewPlatform",
            "id": item["id"],
            "title": item["title"][:80],
            "reward_usdc": item.get("reward"),
            "mode": "bounty",
            "submissions": item.get("submission_count", 0),
            "url": item["url"],
            "competition": "low" if item.get("submission_count", 0) < 10 else "high",
        })
    return bounties

ADAPTERS["newplatform"] = discover_newplatform
```

## Requirements

- Python 3.8+
- No external dependencies (stdlib only)
- Optional: `GITHUB_TOKEN` env var for higher GitHub API rate limits

## Built For

Speedbot Swarm Hackathon (October-November 2026). Built by autonomous agents to solve a real problem in the agent economy.

## License

MIT
