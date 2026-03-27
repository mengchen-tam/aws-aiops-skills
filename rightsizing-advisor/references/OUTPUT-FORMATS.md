# Output Formats

Report templates for rightsizing analysis results.

## Full Report Template

```markdown
# Rightsizing Advisory Report

**Account:** {account_id}
**Region:** {region}
**Analysis Window:** {start_date} ~ {end_date} ({N} days)
**Instances Analyzed:** {count}
**Generated:** {timestamp}

---

## Executive Summary

| Category | Count | Estimated Waste |
|----------|-------|-----------------|
| 🔴 Idle (consider stopping) | X | ~100% |
| 🟠 Over-provisioned (downsize) | X | ~Y% |
| 🟡 Optimization opportunity | X | varies |
| ✅ Well-sized | X | minimal |

**Fleet Efficiency Score:** X% (weighted avg CPU utilization across all instances)

**Key Findings:**
- {finding 1}
- {finding 2}
- {finding 3}

---

## Fleet Overview

| Instance | Class | Engine | vCPU | RAM (GiB) | Peak CPU | Off-Peak CPU | Waste Ratio | Status |
|----------|-------|--------|------|-----------|----------|-------------|-------------|--------|
| {id} | {class} | {engine} | {vcpu} | {ram} | {peak}% | {offpeak}% | {waste}% | {emoji} |

---

## Detailed Analysis

### {emoji} {instance_id} — {status_text}

**Instance Info:**
| Field | Value |
|-------|-------|
| Class | {class} ({vcpu} vCPU, {ram} GiB RAM) |
| Engine | {engine} {version} |
| Storage | {storage_type}, {allocated_gb} GB |
| Multi-AZ | {yes/no} |
| Created | {create_time} |

**Utilization Profile ({N}-day):**

| Period | Avg CPU | Max CPU | Avg Connections | Memory Used |
|--------|---------|---------|-----------------|-------------|
| Overall | {x}% | {x}% | {x} | {x}% |
| Peak hours ({HH:MM}-{HH:MM}) | {x}% | {x}% | {x} | {x}% |
| Off-peak hours | {x}% | {x}% | {x} | {x}% |
| Weekdays | {x}% | {x}% | {x} | - |
| Weekends | {x}% | {x}% | {x} | - |

**Hourly CPU Profile (24h average):**
```
00:00 ██░░░░░░░░  5%
01:00 ██░░░░░░░░  4%
...
09:00 ████████░░  78%
10:00 █████████░  85%
...
22:00 ███░░░░░░░  8%
23:00 ██░░░░░░░░  5%
```

**Waste Analysis:**
- Peak duration: {X}h/day ({Y}% of day)
- Off-peak CPU: {Z}% average
- **Waste ratio: {W}%**

**Recommendations:**

| # | Action | Confidence | Impact |
|---|--------|------------|--------|
| 1 | {recommendation} | {X}% | {description} |
| 2 | {recommendation} | {X}% | {description} |

**Evidence:**
{key metric values supporting the recommendations}

---

## Action Items

### 🔴 Immediate (High Savings, Low Risk)
- [ ] {action}: {instance_id} — {reason}

### 🟠 Short-term (Test First)
- [ ] {action}: {instance_id} — {reason}

### 🟡 Medium-term (Plan & Evaluate)
- [ ] {action}: {instance_id} — {reason}

---

## Reference Documentation

| Topic | URL |
|-------|-----|
| {topic} | {url} |
```

---

## Hourly Profile Visualization

Use simple ASCII bar charts to show the 24-hour pattern:

```
Hour  | CPU Utilization
------+--------------------------------------------------
00:00 | ██░░░░░░░░░░░░░░░░░░  5%
06:00 | ████░░░░░░░░░░░░░░░░  12%
08:00 | ████████████████░░░░  72%    ← peak start
09:00 | ██████████████████░░  85%
10:00 | ██████████████████░░  82%
12:00 | ████████████████░░░░  75%
14:00 | ██████████████░░░░░░  65%    ← peak end
18:00 | ██████░░░░░░░░░░░░░░  18%
22:00 | ███░░░░░░░░░░░░░░░░░  8%
```

Each █ represents ~5%. Show all 24 hours or key hours with annotations.

---

## Status Emoji Guide

| Emoji | Meaning | Action |
|-------|---------|--------|
| 🔴 | Idle — near-zero utilization | Stop or delete |
| 🟠 | Over-provisioned — downsize recommended | Modify instance class |
| 🟡 | Optimization opportunity | Graviton, gp3, RI, etc. |
| ✅ | Well-sized | No action needed |

---

## Evidence Formatting

Always cite specific metric values:

Good:
```
Evidence:
  Peak CPU (avg): 18.3% (09:00-14:00 weekdays)
  Off-Peak CPU (avg): 2.1%
  Max CPU (observed): 34.7% at 2026-03-20 10:15 UTC
  FreeableMemory (avg): 12.4 GiB / 16 GiB (22.5% used)
  DatabaseConnections (peak): 45 / 1300 max (3.5%)
  BurstBalance: N/A (R-family)
  Storage: gp2, 200 GB, 73 GB used (36.5%)
```

Bad:
```
Evidence: CPU is low, memory is fine.
```
