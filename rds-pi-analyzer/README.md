# RDS Performance Insights Analyzer

Analyze RDS Performance Insights data to diagnose slow queries and bottlenecks.

## Quick Start

**Input:**
```
RDS Instance ARN: arn:aws-cn:rds:<region>:<account_id>:db:<instance_id>
DbiResourceId (optional): db-XXXXXXXXXXXXXXXXXXXXXXXXXX
```

**Output:**
- TOP 3 slow queries with optimization recommendations
- Wait event analysis (IO/CPU/Lock breakdown)
- System health assessment (CPU saturation, storage)
- Engine-specific (PostgreSQL/MySQL) fix commands
- Relevant AWS documentation links

## Key Features

- ✅ Adaptive time window — auto-detects peak load periods for focused analysis
- ✅ Engine-aware — PostgreSQL and MySQL specific metrics, syntax, and recommendations
- ✅ Wait event cross-analysis — combines SQL patterns with wait events for root cause identification
- ✅ Fallback analysis — static SQL pattern matching when AdditionalMetrics are unavailable
- ✅ Truncated SQL recovery — fetches full SQL text (up to 4096 chars) via `get-dimension-key-details`
- ✅ Documentation references — queries AWS docs (aws-doc-ecs-remote → aws-knowledge → web search) and includes relevant URLs

## Prerequisites

- Performance Insights enabled on RDS instance (7+ days retention recommended)
- IAM permissions: `pi:DescribeDimensionKeys`, `pi:GetResourceMetrics`, `pi:GetDimensionKeyDetails`, `rds:DescribeDBInstances`, `cloudwatch:GetMetricStatistics`
- AWS API access via one of:
  - MCP server with `call_aws` tool (server name varies by config), or
  - Local AWS CLI installed and configured
- Documentation queries (optional) via one of:
  - MCP `read_documentation` / `search_documentation` tools, or
  - Web search fallback

## Configuration (Optional)

### Cross-Account Setup

To analyze RDS instances across multiple AWS accounts:

1. **Copy the example config:**
   ```bash
   cp config.example.yaml config.yaml
   ```

2. **Edit `config.yaml`** with your account mappings:
   ```yaml
   cross_account:
     enabled: true
     accounts:
       "YOUR_ACCOUNT_ID":
         role_arn: "arn:aws-cn:iam::YOUR_ACCOUNT_ID:role/McpCrossAccountReadOnly"
         description: "Your Account Description"
   ```

3. **Ensure IAM roles exist** in target accounts with permissions:
   - `pi:DescribeDimensionKeys`, `pi:GetResourceMetrics`, `pi:GetDimensionKeyDetails`
   - `rds:DescribeDBInstances`
   - `cloudwatch:GetMetricStatistics`

4. **Trust relationship** (in the target account's role):
   ```json
   {
     "Effect": "Allow",
     "Principal": {
       "AWS": "arn:aws-cn:iam::ANALYZER_ACCOUNT_ID:root"
     },
     "Action": "sts:AssumeRole"
   }
   ```

> **Note:** `config.yaml` contains account IDs — do not commit to public repos.

## Workflow Overview

1. Parse input (ARN → region, account, instance)
2. Get instance info (engine, class, DbiResourceId)
3. Query load trend → auto-detect peak windows (or confirm with user if `auto_select_recommended_window: false`)
4. Query detailed metrics (SQL text, tokenized stats, wait events, storage)
5. Analyze patterns (metrics-based + static SQL fallback + wait event cross-analysis)
6. Generate report (TOP 3 queries, wait events, system health, action items)
7. Engine-specific recommendations (PostgreSQL vs MySQL syntax)
8. Query relevant AWS documentation and include reference URLs

## Supported Engines

| Engine | Version | Additional Metrics |
|--------|---------|-------------------|
| PostgreSQL | 10+ | calls_per_sec, rows_per_call, avg_latency_per_call |
| MySQL | 5.7+, 8.0+ | executions_per_sec, rows_examined_per_exec, db_time_per_exec_us |
| MariaDB | 10.3+ | (inherits MySQL metrics) |

## Limitations

- SQL text truncated at 500 chars in `db.sql` grouping (use `get-dimension-key-details` for up to 4096 chars)
- One-time/failed queries may lack tokenized stats (falls back to static analysis)
- Time granularity: 60 seconds (sub-minute peaks may not be fully captured)
- Confidence scores are pattern-based estimates, not execution plan analysis

## Version

1.1 (2026-03-17)

## License

MIT
