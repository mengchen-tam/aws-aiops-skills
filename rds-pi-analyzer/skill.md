---
name: rds-pi-analyzer
version: 1.1
description: |
  Analyze RDS Performance Insights data to identify slow queries and bottlenecks. 
  Supports PostgreSQL and MySQL with adaptive time window selection.
  
  Use when: (1) Customer reports slow RDS performance, (2) Need to identify TOP SQL 
  causing high DB load, (3) Performance Insights is enabled, (4) Want data-driven 
  optimization recommendations with engine-specific advice.
  
  NOT for: Real-time monitoring (use CloudWatch), detailed execution plans (use EXPLAIN), 
  or when Performance Insights is not enabled.
author: "NWCD TAM Team"
tags: ["rds", "performance-insights", "postgresql", "mysql", "database-optimization"]
---

# RDS Performance Insights SQL Analyzer

Analyze RDS slow queries via Performance Insights API and provide actionable optimization recommendations.

## Overview

This skill helps diagnose RDS performance issues by:
1. Querying Performance Insights metrics (db.load, wait events, top SQL)
2. Analyzing time windows to find peak load periods
3. Identifying bottleneck patterns (not limited to predefined templates)
4. Providing engine-specific (PostgreSQL/MySQL) recommendations

**Important:** The patterns mentioned in this skill (e.g., CROSS JOIN, N+1) are **common examples only**. Real production issues are diverse - always analyze your specific data patterns.

## Prerequisites

- ✅ Performance Insights enabled on target RDS instance (7+ days retention recommended)
- ✅ IAM permissions: `pi:DescribeDimensionKeys`, `pi:GetResourceMetrics`, `pi:GetDimensionKeyDetails`, `rds:DescribeDBInstances`, `cloudwatch:GetMetricStatistics`

### AWS API Access (Tool Selection)

This skill needs to call AWS APIs. Use the first available method:

| Priority | Method | When to Use |
|----------|--------|-------------|
| 1 | MCP `call_aws` tool | MCP server with `call_aws` tool is available (server name varies by client config, e.g., `aws-api-ecs-remote`, `aws-api`, etc.) |
| 2 | Local AWS CLI | No MCP available, but `aws` CLI is installed and configured locally |

**How to detect:**
- Check if any MCP tool named `call_aws` is available in the current session
- If yes → use MCP `call_aws` (supports cross-account `role_arn` parameter natively)
- If no → fall back to local `aws` CLI via shell execution
  - For cross-account: use `aws sts assume-role` first, then export credentials

**For documentation queries (Step 8):**

| Priority | Method | When to Use |
|----------|--------|-------------|
| 1 | MCP `read_documentation` tool | MCP server with `read_documentation` tool is available (e.g., `aws-doc-ecs-remote`) |
| 2 | MCP `search_documentation` tool | MCP server with `search_documentation` tool is available (e.g., `aws-knowledge`) |
| 3 | Web search / fetch | No doc MCP available, use web search tools or direct URL fetch |

**Note:** MCP server names are configured by the user in their `mcp.json` and may vary. The tool names (`call_aws`, `read_documentation`, `search_documentation`) are stable across configurations.

## Workflow

### Step 1: Parse Input

**Input format:**
```
RDS Instance ARN: arn:aws-cn:rds:cn-northwest-1:111111111111:db:prod-db-01
Time window (optional): 1h / 24h / custom range
```

Extract: region, account_id, instance_id

### Step 2: Get Instance Info

**Query RDS instance details:**
```bash
aws rds describe-db-instances \
  --db-instance-identifier <instance_id> \
  --region <region>
```

**Extract:**
- DbiResourceId (required for PI API)
- Engine (postgres/mysql/mariadb)
- DBInstanceClass (e.g., db.t3.micro)
- AllocatedStorage
- PerformanceInsightsEnabled (must be true)

**Calculate vCPU count:**
- db.t3.micro/small: 2 vCPU
- db.t3.medium: 2 vCPU
- db.t3.large: 2 vCPU
- db.t3.xlarge: 4 vCPU
- db.m5/r5: refer to instance specs

### Step 3: Query Load Trend (Initial Window)

**Query db.load.avg over 1 hour (or user-specified window):**
```bash
aws pi get-resource-metrics \
  --service-type RDS \
  --identifier <DbiResourceId> \
  --start-time <now - 1h> \
  --end-time <now> \
  --period-in-seconds 60 \
  --metric-queries '[{"Metric": "db.load.avg"}]' \
  --region <region>
```

**Analyze trend:**
- Calculate: mean, max, std_dev
- Detect peaks: values > (mean + 2*std_dev) or > (vCPU * 0.8)
- Identify peak windows (continuous high-load periods)

**Generate window recommendations:**
```
Option 1: Peak window (e.g., 14:00-14:15) - highest load detected
Option 2: Last 30 minutes - recent activity
Option 3: Full 1 hour - broader context
Option 4: Custom range
```

**Window selection behavior:**
- If `config.yaml` → `analysis.auto_select_recommended_window: true`: Automatically use the peak window and note the selection in the report.
- If `auto_select_recommended_window: false`: Present options to user and wait for confirmation before proceeding.
- Always log which window was selected and why in the report header.

### Step 4: Query Detailed Metrics (Confirmed Window)

#### 4.1 Get Full SQL Text

**Query with db.sql grouping:**
```bash
aws pi describe-dimension-keys \
  --service-type RDS \
  --identifier <DbiResourceId> \
  --metric db.load.avg \
  --start-time <confirmed_start> \
  --end-time <confirmed_end> \
  --group-by Group=db.sql \
  --max-results 10 \
  --region <region>
```

**Extract:** SQL ID, full statement (may be truncated at 500 chars), db.load contribution

**Handle truncated SQL (>500 chars):**
If any SQL statement appears truncated (ends abruptly mid-word or at exactly ~500 chars), fetch the full text:
```bash
aws pi get-dimension-key-details \
  --service-type RDS \
  --identifier <DbiResourceId> \
  --group Group=db.sql \
  --group-identifier <db.sql.id> \
  --requested-dimensions "db.sql.statement" \
  --region <region>
```
This returns the full SQL text (up to 4096 chars). Use this for accurate pattern analysis.

#### 4.2 Get Additional Metrics

**Query with db.sql_tokenized grouping:**

**For PostgreSQL:**
```bash
aws pi describe-dimension-keys \
  --service-type RDS \
  --identifier <DbiResourceId> \
  --metric db.load.avg \
  --start-time <confirmed_start> \
  --end-time <confirmed_end> \
  --group-by Group=db.sql_tokenized \
  --additional-metrics '["db.sql_tokenized.stats.calls_per_sec","db.sql_tokenized.stats.rows_per_call","db.sql_tokenized.stats.avg_latency_per_call"]' \
  --max-results 20 \
  --region <region>
```

**For MySQL:**
```bash
# Use: executions_per_sec, rows_examined_per_exec, db_time_per_exec_us
--additional-metrics '["db.sql_tokenized.stats.executions_per_sec","db.sql_tokenized.stats.rows_examined_per_exec","db.sql_tokenized.stats.db_time_per_exec_us"]'
```

**Note:** One-time queries (e.g., long-running COPY, failed transactions) may not have tokenized stats. Use static SQL analysis as fallback.

#### 4.3 Get Wait Events

**Query wait event breakdown:**
```bash
aws pi describe-dimension-keys \
  --service-type RDS \
  --identifier <DbiResourceId> \
  --metric db.load.avg \
  --start-time <confirmed_start> \
  --end-time <confirmed_end> \
  --group-by Group=db.wait_event \
  --max-results 10 \
  --region <region>
```

**Extract:** Wait event name, type (IO/CPU/Lock/Client), db.load contribution

#### 4.4 Check Storage Space (Optional)

```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name FreeStorageSpace \
  --dimensions Name=DBInstanceIdentifier,Value=<instance_id> \
  --start-time <confirmed_start> \
  --end-time <confirmed_end> \
  --period 300 \
  --statistics Average Minimum Maximum \
  --region <region>
```

**Why all three statistics:**
- `Average`: Overall trend during the period
- `Minimum`: Captures lowest free space point (e.g., during temp file spikes from sort/hash operations)
- `Maximum`: Baseline free space before load

### Step 5: Analyze Patterns

**For each SQL query, combine:**
- SQL text
- db.load contribution
- Additional metrics (if available)
- Wait events (cross-reference)

**Detection strategies:**

#### 5.1 With Additional Metrics (Preferred)

**High execution frequency:**
```
calls_per_sec > 100 AND rows_per_call < 10
→ Possible N+1 pattern or high-frequency small queries
```

**High rows scanned:**
```
rows_per_call > 10,000
→ Possible full table scan (missing index)
```

**High latency:**
```
avg_latency_per_call > 1000ms
→ Slow query (needs optimization)
```

#### 5.2 Without Additional Metrics (Fallback - Static Analysis)

**SQL text pattern matching:**
- `CROSS JOIN` → Cartesian product (confidence: 90%)
- `(SELECT ... WHERE outer.col = inner.col)` → Correlated subquery (confidence: 80%)
- `SELECT *` + high db.load → Unnecessary columns (confidence: 60%)
- `UPDATE/DELETE` without `WHERE` → Full table operation (confidence: 95%)

**Clearly state in report:** "Analysis based on SQL text pattern (AdditionalMetrics unavailable)"

#### 5.3 Wait Event Cross-Analysis

**Combine SQL with wait events to identify root cause:**

| Wait Event | + SQL Pattern | Likely Cause |
|-----------|--------------|--------------|
| IO:DataFileRead | rows > 10K | Full table scan - add index |
| IO:BufFileWrite | ORDER BY/GROUP BY | work_mem too small |
| Lock:transactionid | UPDATE/DELETE | Lock contention - check long transactions |
| CPU | Complex JOIN/functions | CPU-intensive - optimize logic |
| Client:ClientWrite | SELECT * | Network bottleneck - reduce columns |

**Example real scenario:**
- Peak load: 7:00-10:00 daily
- Wait event: Lock:relation (high)
- Cause: Scheduled batch job holding locks
- Recommendation: Check cron jobs, optimize job scheduling

### Step 6: Generate Report

**Report structure:**

```markdown
# RDS Performance Insights Analysis

**Instance:** <instance_id>
**Engine:** <engine> <version>
**Class:** <instance_class> (<vcpu> vCPU, <ram> GB RAM)
**Analysis Window:** <start> ~ <end> (<duration>)

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Peak DB Load | <max_load> AAS |
| CPU Saturation | <saturation>% (<load>/<vcpu>) |
| Analyzed Queries | <count> |
| Slow Queries (>1s) | <count> |

**Key Findings:**
- <Bottleneck 1>
- <Bottleneck 2>
- <System-level issue (if any)>

---

## TOP 3 Queries (by DB Load)

### 1. <Query Description> (DB Load: <value> AAS, <pct>%)

**SQL:**
```sql
<full or truncated SQL>
```

**Metrics:**
- Execution frequency: <calls_per_sec> calls/sec (if available)
- Avg latency: <latency> ms (if available)
- Rows per call: <rows> (if available)

**Wait Event Breakdown:**
- <event>: <load> (<pct>%)

**Analysis:**
<What's wrong - data-driven, not template-based>

**Recommendation:**
<Specific fix - engine-appropriate>

**Reference:**
- [<Doc title>](<URL>)

---

## Wait Event Analysis

| Event | DB Load | % | Type |
|-------|---------|---|------|
| <event> | <load> | <pct> | <interpretation> |

**Interpretation:**
<Overall bottleneck type: IO/CPU/Lock/Mixed>

---

## System Health

**CPU Saturation:** <load>/<vcpu> = <pct>%
- ✅ Normal (<80%) / ⚠️ High (80-150%) / 🔴 Critical (>150%)

**Storage Space:** <free>/<total> GB (<pct>% free)
- ✅ Sufficient (>20%) / ⚠️ Low (10-20%) / 🔴 Critical (<10%)

**Recommendations:**
- [ ] <System-level action if needed>

---

## Action Items

### High Priority (Immediate)
- [ ] <Action 1>
- [ ] <Action 2>

### Medium Priority (1-2 weeks)
- [ ] <Action 3>

### Monitoring
- [ ] Track db.load trend after fixes
- [ ] Set CloudWatch alarm if db.load > <threshold>

---

**Generated:** <timestamp>
**Next Review:** <suggest date>
```

### Step 7: Engine-Specific Recommendations

**PostgreSQL:**
- Index: `CREATE INDEX CONCURRENTLY ...`
- Check indexes: `SELECT * FROM pg_indexes WHERE tablename = '...'`
- Explain: `EXPLAIN (ANALYZE, BUFFERS) ...`
- Locks: `SELECT * FROM pg_locks WHERE NOT granted`
- Docs: https://docs.amazonaws.cn/.../CHAP_PostgreSQL.html

**MySQL:**
- Index: `CREATE INDEX ...`
- Check indexes: `SHOW INDEX FROM table`
- Explain: `EXPLAIN ...`
- Locks: `SHOW ENGINE INNODB STATUS`
- Docs: https://docs.amazonaws.cn/.../CHAP_MySQL.html

### Step 8: Query Relevant Documentation

**After generating the report, query AWS documentation to provide actionable reference URLs for each recommendation.**

Use the following tool priority order to find relevant docs:

#### Priority 1: aws-doc-ecs-remote (China Region Docs — Preferred)

For cn-northwest-1 / cn-north-1 regions, use `aws_doc_ecs_remote.read_documentation` to directly read China-region documentation pages. This is the fastest and most reliable method.

**Common documentation pages by issue type:**

| Issue Type | Documentation URL |
|-----------|------------------|
| General best practices | `https://docs.amazonaws.cn/en_us/AmazonRDS/latest/UserGuide/CHAP_BestPractices.html` |
| Instance sizing / upgrade | `https://docs.amazonaws.cn/en_us/AmazonRDS/latest/UserGuide/Overview.DBInstance.Modifying.html` |
| Performance Insights usage | `https://docs.amazonaws.cn/en_us/AmazonRDS/latest/UserGuide/USER_PerfInsights.html` |
| PI counter metrics | `https://docs.amazonaws.cn/en_us/AmazonRDS/latest/UserGuide/USER_PerfInsights.UsingDashboard.AnalyzeDBLoad.AdditionalMetrics.html` |
| PostgreSQL tuning | `https://docs.amazonaws.cn/en_us/AmazonRDS/latest/UserGuide/CHAP_PostgreSQL.html` |
| MySQL tuning | `https://docs.amazonaws.cn/en_us/AmazonRDS/latest/UserGuide/CHAP_MySQL.html` |
| Parameter groups | `https://docs.amazonaws.cn/en_us/AmazonRDS/latest/UserGuide/USER_WorkingWithParamGroups.html` |
| Monitoring overview | `https://docs.amazonaws.cn/en_us/AmazonRDS/latest/UserGuide/CHAP_Monitoring.html` |
| Storage management | `https://docs.amazonaws.cn/en_us/AmazonRDS/latest/UserGuide/USER_PIOPS.StorageTypes.html` |
| Read replicas | `https://docs.amazonaws.cn/en_us/AmazonRDS/latest/UserGuide/USER_ReadRepl.html` |

**Usage:** Read the page, extract the specific section relevant to the issue, and include the URL in the report.

#### Priority 2: aws-knowledge MCP (Search-based)

If the specific doc URL is unknown, or you need to find docs for an uncommon issue, use `aws___search_documentation`:

```
# Search examples by issue type:

# Wait event interpretation:
search_phrase: "RDS PostgreSQL wait events troubleshooting"
topics: ["troubleshooting"]

# Storage issues:
search_phrase: "RDS storage full temporary files PostgreSQL"
topics: ["troubleshooting"]

# Parameter tuning:
search_phrase: "RDS PostgreSQL parameter group work_mem tuning"
topics: ["reference_documentation"]

# Instance class comparison:
search_phrase: "RDS instance class comparison PostgreSQL performance"
topics: ["general"]
```

#### Priority 3: Web Search (Fallback)

If neither aws-doc nor aws-knowledge returns useful results (e.g., for community best practices, third-party tools, or very specific edge cases), use web search as a last resort.

#### Include in Report

Add a "Reference Documentation" section at the end of the report:

```markdown
## Reference Documentation

| Topic | URL | Relevance |
|-------|-----|-----------|
| <topic> | <url> | <why this doc is relevant to the findings> |
```

**Rules:**
- Only include docs directly relevant to the issues found (3-6 docs max)
- For cn-* regions: prefer `docs.amazonaws.cn` URLs
- For global regions: prefer `docs.aws.amazon.com` URLs
- Verify URLs are accessible by reading them before including

---

## Common Patterns (Examples Only)

**Note:** These are common patterns we've observed, but production issues are diverse. Always analyze your specific data.

### Pattern 1: Cartesian Product (CROSS JOIN)
- **Detection:** SQL contains `CROSS JOIN`
- **Impact:** Massive intermediate result sets
- **Fix:** Replace with `INNER JOIN` + ON condition

### Pattern 2: Correlated Subquery (SQL-level N+1)
- **Detection:** `(SELECT ... WHERE outer.id = inner.id)` pattern
- **Impact:** Repeated table scans
- **Fix:** Rewrite as `LEFT JOIN` + `GROUP BY`

### Pattern 3: Missing Index
- **Detection:** `rows_per_call > 10,000` + `IO:DataFileRead` wait
- **Impact:** Full table scans on large tables
- **Fix:** Add index on WHERE/JOIN columns

### Pattern 4: Scheduled Job Lock Contention
- **Detection:** Peak load at specific daily times + `Lock:*` wait events
- **Impact:** Batch jobs blocking interactive queries
- **Fix:** Optimize job scheduling, reduce lock duration

### Pattern 5: work_mem Overflow
- **Detection:** `IO:BufFileWrite` + queries with ORDER BY/GROUP BY
- **Impact:** Sort/hash operations spill to disk
- **Fix:** Increase `work_mem` parameter or add supporting indexes

## Limitations

- **Time window accuracy:** Short-lived peaks (<1 min) may not be fully captured in 60-second granularity
- **SQL truncation:** Statements >500 chars are truncated in `db.sql` grouping. Use `pi get-dimension-key-details` to fetch full text (up to 4096 chars).
- **AdditionalMetrics availability:** One-time or failed queries may not have tokenized stats
- **Pattern detection:** Not exhaustive - use as guidance, not definitive diagnosis

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `InvalidResourceStateFault` | PI not enabled | Enable via RDS console |
| `AccessDenied` | Missing IAM perms | Add `pi:*`, `rds:*`, `cloudwatch:*` |
| `ThrottlingException` | API rate limit | Retry after 5 seconds (max 2 retries) |
| Empty AdditionalMetrics | One-time query | Use static SQL analysis fallback |

## Best Practices

1. **Always check trends first:** Understand load pattern before deep-diving into SQL
2. **Cross-reference wait events:** Don't rely solely on SQL text
3. **Engine-specific syntax:** Use correct commands for PostgreSQL vs MySQL
4. **Test before production:** Validate index/query changes in staging
5. **Monitor after changes:** Track db.load for 24-48 hours post-fix
6. **Document anomalies:** Note time-based patterns (e.g., daily 7-10am peaks)


## License

MIT
