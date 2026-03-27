---
name: rightsizing-advisor
version: 1.0
description: |
  Analyze AWS resource utilization patterns and provide rightsizing recommendations.
  Scans all instances in a target account, identifies peak/off-peak patterns, quantifies
  idle waste, and recommends optimization actions (downsize, Graviton migration, Aurora
  Serverless v2, Reserved Instances, storage optimization).

  Use when: (1) Customer wants to reduce database costs, (2) Need to find underutilized
  or idle RDS instances, (3) Periodic capacity review / rightsizing assessment,
  (4) Customer has obvious peak/off-peak traffic patterns and suspects over-provisioning.
  Make sure to use this skill whenever the user mentions rightsizing, cost optimization,
  idle databases, underutilized instances, capacity review, resource waste, or wants to
  analyze CloudWatch metrics for database fleet efficiency — even if they don't explicitly
  say "rightsizing".

  Currently supports: RDS (MySQL, PostgreSQL, MariaDB, Aurora).
  Planned: ElastiCache, DocumentDB.
compatibility:
  requires_tools: ["call_aws", "execute_bash"]
  requires_python: ">=3.10"
author: "AWS TAM Team"
tags: ["cost-optimization", "rightsizing", "rds", "cloudwatch", "capacity-planning"]
---

# Rightsizing Advisor

Scan AWS database resources, analyze utilization patterns, and generate rightsizing recommendations.

## Overview

Many customers run database instances sized for peak load 24/7, but actual peak windows
may only be a few hours per day. This skill:

1. Scans all instances of the target service in a target account
2. Collects CloudWatch metrics over a configurable window (default 7 days, up to 30)
3. Identifies peak vs off-peak time patterns (workday/weekend, day/night)
4. Quantifies waste: how much capacity sits idle and for how long
5. Recommends specific optimization actions with confidence levels

**Key principle:** Never recommend downsizing that would impact peak-hour performance.
All recommendations preserve headroom for the busiest observed period.

## Prerequisites

- CloudWatch retains 1-minute data for 15 days, 5-minute for 63 days, 1-hour for 455 days
- No Performance Insights required (pure CloudWatch analysis)
- Service-specific IAM permissions — see each service's reference file
- **Python 3.10+ required locally** for metric collection scripts (see Environment Setup below)

## Environment Setup

**This skill requires a local Python environment to run metric collection scripts.**
Before starting analysis, check if the environment is ready. If not, guide the user
through setup.

**Check:**
```bash
ls <skill-dir>/rightsizing-advisor/.venv/bin/python 2>/dev/null && echo "OK" || echo "NEEDS SETUP"
```

**Setup (one-time):**
```bash
cd <skill-dir>/rightsizing-advisor
python3 -m venv .venv
.venv/bin/pip install -r scripts/requirements.txt
```

**If Python is not available on the system**, inform the user:
> "This skill requires Python 3.10+ to run metric collection scripts locally.
> The scripts connect to your MCP server to batch-fetch CloudWatch metrics and
> aggregate them — this avoids sending hundreds of thousands of raw datapoints
> through the AI context. Please install Python and re-run."

## Configuration

**CRITICAL: Always load config.yaml first.**

config.yaml structure:

    cross_account:
      accounts:
        "123456789012":
          role_arn: "arn:aws-cn:iam::123456789012:role/RoleName"
          regions: ["cn-northwest-1"]

    analysis:
      lookback_days: 7          # 7, 14, or 30
      services: ["rds"]         # Supported: rds. Planned: elasticache, documentdb

Workflow:
1. Read config.yaml
2. Find target account ID (from user request or config)
3. Extract role_arn and regions
4. Use role_arn in ALL call_aws tool calls

**Never hardcode role ARNs.**

## Service-Specific References

**CRITICAL: Always read the relevant reference file before analyzing a service.**

| Service | Reference File | Script | Status |
|---------|---------------|--------|--------|
| RDS | references/RDS.md | scripts/collect_rds_metrics.py | ✅ Supported |
| ElastiCache | references/ELASTICACHE.md | scripts/collect_elasticache_metrics.py | 🔜 Planned |
| DocumentDB | references/DOCUMENTDB.md | scripts/collect_documentdb_metrics.py | 🔜 Planned |

## Core Workflow

### Step 1: Discover Instances (via MCP call_aws)

**Use call_aws directly** to list all instances in the target account/region.

**RDS example:**
```
call_aws(
    cli_command="aws rds describe-db-instances --no-paginate --region cn-northwest-1",
    role_arn="<from config.yaml>"
)
```

**For each instance, extract:**
- Instance identifier and ARN
- Instance class → map to vCPU and memory (see service reference file)
- Engine/version
- Storage type and size
- Multi-AZ status
- Status (skip non-running instances)

**Present fleet summary to user and ask for confirmation:**

For Aurora instances, also fetch cluster info to identify writer/reader roles:
```
call_aws(
    cli_command="aws rds describe-db-clusters --no-paginate --region cn-northwest-1",
    role_arn="<from config.yaml>"
)
```

Group Aurora instances by `DBClusterIdentifier` and note each member's role
(`IsClusterWriter: true/false` from the cluster's `DBClusterMembers` array).

```
Found X instances in account XXXXXXXXXXXX (cn-northwest-1):

| # | Instance | Class | Engine | vCPU | RAM | Storage | Multi-AZ |
|---|----------|-------|--------|------|-----|---------|----------|
| 1 | prod-db  | db.r5.xlarge | mysql 8.0 | 4 | 32 GiB | gp3 100GB | Yes |
| 2 | dev-db   | db.t3.medium | postgres 15 | 2 | 4 GiB | gp2 50GB | No |

Options:
1. Analyze ALL instances (default)
2. Select specific instances (e.g., "1,3,5" or "prod-db")
3. Adjust lookback window (default: 7 days, options: 7/14/30)

Which instances to analyze, and how many days?
```

**Wait for user confirmation before proceeding to Step 2.**

---

### Step 2: Collect & Aggregate Metrics (via Script)

**Use the data collection script** to fetch CloudWatch metrics and aggregate locally.
This avoids flooding the context with raw datapoints (~100KB+ → ~3KB summary).

The script:
- Connects to the MCP server endpoint
- Calls `call_aws` via MCP to fetch CloudWatch data
- Fetches in day-sized batches (1-minute granularity, 1440 pts/day) to support any lookback window
- Aggregates locally and outputs compact JSON summary

#### Script Setup

If the venv doesn't exist yet, run the setup from **Environment Setup** section above.

#### Identify MCP Endpoint

Read the MCP config to find the aws-api server endpoint. The config is typically at
`~/.kiro/settings/mcp.json` (Kiro) or equivalent for other AI assistants.

Look for the server entry that provides the `call_aws` tool (usually has "aws-api" in the name).
Extract its `url` and `headers.Authorization` (if present).

#### Run the Script

**Read the service-specific reference file (e.g., references/RDS.md) for the full script
command, parameters, and output field interpretation.**

The reference file contains:
- Complete command-line usage with all parameters
- Output field descriptions and how to interpret each one
- Service-specific notes (e.g., Aurora cluster handling)

**The script outputs JSON to stdout.** Capture it for analysis in Step 3.

**If the script is unavailable** (no Python, no venv), fall back to calling `call_aws`
directly for 1-2 key metrics at a time. Use `--period 3600` for 7-day windows to stay
under the 1440 limit, and manually compute summary stats.

---

### Step 3: Time Pattern Analysis

**Using the script's JSON output**, analyze the patterns:

#### 3.1 Hourly Profile
The script provides `hourly_profile` (24-hour averages) for each metric.
Identify which hours have elevated CPU/connections.

#### 3.2 Peak/Off-Peak
The script provides `peak_analysis` with one of:
- `"steady_state"` — flat utilization, no clear peak/off-peak
- `"variable"` — clear peak hours identified, with `peak_cpu_avg` and `offpeak_cpu_avg`
- `"no_data"` — insufficient data

#### 3.3 Weekday/Weekend
The script provides `weekday_weekend` split for each metric.
Compare weekday vs weekend averages.

#### 3.4 Idle Detection
The script provides `idle_detection` with `is_idle` flag.
An instance is idle if max CPU < 5% AND max connections < 2.

---

### Step 4: Utilization Scoring

**From the script output, extract:**

| Metric | Source | Interpretation |
|--------|--------|----------------|
| Peak CPU % | peak_analysis.peak_cpu_avg | How hard it works at peak |
| Off-Peak CPU % | peak_analysis.offpeak_cpu_avg | How idle it is off-peak |
| Waste Ratio | waste_ratio_pct | % of capacity wasted |
| Memory Util | memory.pct | Memory usage % |
| Storage Util | storage.pct | Disk usage % |
| Is Idle | idle_detection.is_idle | Near-zero activity |

---

### Step 5: Generate Recommendations

**Read the service-specific reference file for detailed optimization paths.**

Generic recommendation categories:

| Category | Condition | Action |
|----------|-----------|--------|
| 🔴 Idle | is_idle=true | Stop or delete |
| 🟠 Severely over-provisioned | peak CPU < 20% | Downsize by 2 levels |
| 🟠 Moderately over-provisioned | peak CPU 20-40% | Downsize by 1 level |
| 🟡 High variance pattern | peak CPU > 60%, off-peak < 10% | Auto-scaling / scheduled scaling |
| 🟡 Graviton opportunity | running x86 instance family | Migrate to Graviton |
| 🟡 Generation upgrade | running older generation | Upgrade to latest gen |
| 🟡 Storage optimization | service-specific | See reference file |
| 🟡 Reserved capacity | steady-state, running > 30 days | Purchase RI / Savings Plan |
| ✅ Well-sized | peak CPU 40-80% | No action needed |

**Safety rules:**
- Never recommend downsizing without checking memory utilization
- Never recommend downsizing if it would breach peak-hour headroom
- Multiple recommendations can stack (e.g., downsize + Graviton + storage)
- Always provide evidence (specific metric values)

---

### Step 6: Generate Report

**Read references/OUTPUT-FORMATS.md for the full report template.**

Report structure:

```markdown
# Rightsizing Advisory Report

**Account:** <account_id>
**Region:** <region>
**Analysis Window:** <start> ~ <end> (<N> days)
**Instances Analyzed:** <count>
**Generated:** <timestamp>

## Executive Summary
[Fleet-level stats: idle/over-provisioned/optimizable/well-sized counts]

## Fleet Overview
[Table: all instances with key metrics and status]

## Detailed Analysis
[Per-instance: utilization profile, waste ratio, recommendations with evidence]

## Action Items
[Priority-sorted: 🔴 immediate → 🟠 short-term → 🟡 medium-term]
```

**Save report to:** `report/rightsizing-<account_id>-<date>.md`

---

### Step 7: Query Documentation (Optional)

After generating the report, query AWS documentation for relevant references
based on the recommendations made. Include doc URLs in the report.

## Mandatory Analysis Policy

**For EVERY instance in scope:**

1. ✅ Collect all core CloudWatch metrics (via script)
2. ✅ Review hourly utilization profile
3. ✅ Classify peak/off-peak pattern
4. ✅ Calculate waste ratio
5. ✅ Generate at least one recommendation (even if "well-sized")
6. ✅ Provide evidence (specific metric values from script output)

**Do not:**
- Skip instances because they "look fine"
- Recommend downsizing without checking peak utilization AND memory
- Make service-specific recommendations without reading the reference file
- Guess thresholds — use values from the reference file

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| AccessDenied | Missing IAM perms | Check service reference for required permissions |
| Script not found | venv not set up | Run setup commands (see Step 2) |
| MCP connection failed | Wrong URL/token | Re-read mcp.json for correct endpoint |
| No datapoints | Instance just created | Note in report, skip analysis |
| Throttling | Too many API calls | Script has built-in throttle protection |

## Tool Usage

Use call_aws tool for resource discovery (Step 1).
Use execute_bash to run collection scripts (Step 2).

    call_aws(
        cli_command="aws <service> <operation> <parameters> --region <region>",
        role_arn="<from config.yaml>"
    )

## Important Notes

- CloudWatch metrics are free to query (included with most services)
- 1-minute data retained 15 days, 5-minute for 63 days, 1-hour for 455 days
- Script uses 1-minute granularity with day-batching for maximum precision
- Always use UTC timestamps for consistency
- Memory metrics are in bytes — script converts to GiB automatically
- Multi-AZ / replicated deployments cost more — factor into savings estimates
