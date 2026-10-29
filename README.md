# Multi-Platform Bounty Hunter for AI Agents

Auto-discovers and matches paid bounties across TaskMarket, Speedbot, Algora, GitHub and more.

## Usage

```bash
python bounty_hunter.py scan
python bounty_hunter.py scan --min-reward 5
python bounty_hunter.py platforms
python bounty_hunter.py watch --interval 300
```

## Platform Adapters

1. TaskMarket - bounty-mode tasks, no stake, skips submitted IDs, drops expired
2. Speedbot - Swarm Hackathon, Weekly Active, Hosted API Bounty, find_paid_work aggregator
3. DAiL - open bounty endpoint

## Verified Output

```
6 opportunities ($183.00 total)
  1. $125.00 | Superteam Earn | RaptorX Research Challenge
  2. $ 50.00 | Speedbot | Swarm Hackathon
  3. $  2.00 | Taskmarket | A Pocket Binary Lantern
```

## Requirements

Python 3.8+ (stdlib only - no pip install)
