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
author: "NWCD TAM Team"
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

**Using the script's JSON output**, analyze the patterns.
The script pre-computes all pattern analysis — field meanings and interpretation
rules are documented in the service-specific reference file (e.g., references/RDS.md).

The script output typically includes:

- **Pattern classification** — workload shape (steady, variable, spiky)
- **Idle detection** — whether the instance has near-zero activity
- **Spike detection** — whether short bursts far exceed the average
- **Utilization summaries** — memory, storage, IOPS where applicable
- **Waste ratio** — estimated % of capacity underutilized

**Always read the reference file for the exact field names, thresholds, and
interpretation rules for the specific service.**

---

### Step 4: Utilization Scoring

The script output contains pre-computed utilization metrics and flags.
Refer to the service-specific reference file for:

- Which fields to check and what they mean
- How to cross-reference CPU avg vs max vs memory before recommending downsizing
- Service-specific caveats (e.g., Aurora storage, T-family burst credits)

---

### Step 5: Generate Recommendations

**Read the service-specific reference file for detailed optimization paths, thresholds,
and service-specific recommendations (e.g., Aurora Serverless, Graviton, storage types).**

Based on the script output, classify each instance into one of these categories:

| Category | How to Identify | General Direction |
|----------|----------------|-------------------|
| 🔴 Idle | `is_idle=true` | Stop or delete |
| 🟠 Over-provisioned | Low avg CPU, no spike_warning, low memory % | Downsize (see reference for how many levels) |
| 🟡 Optimization opportunity | Service-specific (architecture, generation, pricing) | See reference file |
| ✅ Well-sized | Moderate CPU utilization at peak | No action needed |

**Decision flow for each instance:**

1. Check idle detection → if idle, recommend stop/delete
2. Check spike detection → if present, do NOT base downsizing on avg CPU alone
3. Check workload pattern:
   - variable → consider auto-scaling or scheduled scaling
   - spiky → investigate burst source before any changes
   - steady_state → candidate for Reserved Instance / Savings Plan
4. Read service reference file for specific optimization paths (e.g., Graviton migration,
   storage type changes, cluster topology changes)
5. Cross-check memory/storage utilization before finalizing

**Safety rules:**
- Always check CPU max (not just avg) before recommending downsizing
- Always check memory utilization — low CPU doesn't mean the instance can shrink if memory is tight
- Read the service reference file for service-specific pitfalls (e.g., Aurora storage, T-family burst)
- Multiple recommendations can stack — present them in priority order
- Every recommendation must cite specific metric values as evidence

---

### Step 6: Generate Report

**Read references/OUTPUT-FORMATS.md for the full report template.**

Report structure:

```markdown
# Rightsizing Advisory Report

**Account:** <account_id>
**Region:** <region>
**Analysis Window:** <N> days
**Instances Analyzed:** <count>
**Generated:** <timestamp>

## Executive Summary
[Fleet-level stats: idle/over-provisioned/optimizable/well-sized counts]

## Fleet Overview
[Table: all instances with key metrics and status]

## Detailed Analysis
[Per-instance: key metrics, pattern, recommendations with evidence]

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

1. ✅ Collect metrics via service-specific script
2. ✅ Review script output: pattern, idle detection, spike warning
3. ✅ Read service reference file for interpretation rules
4. ✅ Generate at least one recommendation (even if "well-sized")
5. ✅ Provide evidence (cite specific metric values from script output)

**Do not:**
- Skip instances because they "look fine"
- Recommend downsizing based on avg CPU alone — always check max and memory
- Make service-specific recommendations without reading the reference file
- Assume thresholds are the same across services

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| AccessDenied | Missing IAM perms | Check service reference for required permissions |
| Script not found | venv not set up | Run setup commands (see Environment Setup) |
| MCP connection failed | Wrong URL/token | Re-read mcp.json for correct endpoint |
| No datapoints | Instance just created or stopped | Note in report, skip analysis |
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
- Script uses 1-minute granularity with day-batching for maximum precision
- Memory metrics are in bytes — script converts to GiB automatically
- Clustered services (Aurora, ElastiCache) should be analyzed at cluster level — see reference file
