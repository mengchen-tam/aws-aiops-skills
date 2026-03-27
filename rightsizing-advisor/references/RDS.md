# RDS Rightsizing Reference

Service-specific details for analyzing Amazon RDS instances (MySQL, PostgreSQL, MariaDB, Aurora).

## Prerequisites

IAM permissions required:
- `rds:DescribeDBInstances`
- `rds:DescribeReservedDBInstances`
- `cloudwatch:GetMetricStatistics`
- `cloudwatch:GetMetricData`

---

## Step 1: Discover Instances

```bash
aws rds describe-db-instances --no-paginate --region <region>
```

**Extract per instance:**

| Field | Path | Notes |
|-------|------|-------|
| Instance ID | DBInstanceIdentifier | Primary key |
| Class | DBInstanceClass | e.g., db.r5.xlarge |
| Engine | Engine | mysql, postgres, mariadb, aurora-mysql, aurora-postgresql |
| Version | EngineVersion | Check for Extended Support (Path 8) |
| Lifecycle | EngineLifecycleSupport | `open-source-rds-extended-support` = extra charges |
| Multi-AZ | MultiAZ | true = 2x cost (Path 9) |
| Storage Type | StorageType | gp2/gp3/io1/io2/aurora |
| Storage Size | AllocatedStorage | GB (meaningless for Aurora, always 1) |
| Status | DBInstanceStatus | Skip if not "available" |
| Created | InstanceCreateTime | For RI eligibility check |
| Cluster | DBClusterIdentifier | Group Aurora instances by cluster |
| Replicas | ReadReplicaDBInstanceIdentifiers | Check for idle replicas (Path 10) |

---

## Step 2: Instance Type Specifications

### vCPU and Memory Mapping

| Class | vCPU | RAM (GiB) | Family | Notes |
|-------|------|-----------|--------|-------|
| db.t3.micro | 2 | 1 | Burstable | Dev/test only |
| db.t3.small | 2 | 2 | Burstable | |
| db.t3.medium | 2 | 4 | Burstable | |
| db.t3.large | 2 | 8 | Burstable | |
| db.t3.xlarge | 4 | 16 | Burstable | |
| db.t3.2xlarge | 8 | 32 | Burstable | |
| db.t4g.micro | 2 | 1 | Burstable/Graviton | |
| db.t4g.medium | 2 | 4 | Burstable/Graviton | |
| db.t4g.large | 2 | 8 | Burstable/Graviton | |
| db.m5.large | 2 | 8 | General Purpose | |
| db.m5.xlarge | 4 | 16 | General Purpose | |
| db.m5.2xlarge | 8 | 32 | General Purpose | |
| db.m5.4xlarge | 16 | 64 | General Purpose | |
| db.m6g.large | 2 | 8 | GP/Graviton | |
| db.m6g.xlarge | 4 | 16 | GP/Graviton | |
| db.m7g.large | 2 | 8 | GP/Graviton | |
| db.m7g.xlarge | 4 | 16 | GP/Graviton | |
| db.r5.large | 2 | 16 | Memory Optimized | |
| db.r5.xlarge | 4 | 32 | Memory Optimized | |
| db.r5.2xlarge | 8 | 64 | Memory Optimized | |
| db.r5.4xlarge | 16 | 128 | Memory Optimized | |
| db.r5.8xlarge | 32 | 256 | Memory Optimized | |
| db.r6g.large | 2 | 16 | MemOpt/Graviton | |
| db.r6g.xlarge | 4 | 32 | MemOpt/Graviton | |
| db.r7g.large | 2 | 16 | MemOpt/Graviton | |
| db.r7g.xlarge | 4 | 32 | MemOpt/Graviton | |
| db.r7g.2xlarge | 8 | 64 | MemOpt/Graviton | |

**Rule:** Within a family, each size step doubles both vCPU and memory.
For unlisted types, look up from describe-db-instances or AWS docs.

### T-Family Burst Behavior

T3/T4g instances use CPU credit system:
- Each type has a **baseline CPU %** (sustainable without consuming credits)
- BurstBalance metric shows remaining credits (0-100%)

| Class | Baseline CPU % |
|-------|----------------|
| db.t3.micro | 10% |
| db.t3.small | 20% |
| db.t3.medium | 20% |
| db.t3.large | 30% |
| db.t3.xlarge | 40% |

**Analysis rules for T-family:**
- BurstBalance consistently > 80% → over-provisioned (not using burst capacity)
- BurstBalance drops to 0 → under-provisioned, consider M/R family
- Always collect BurstBalance metric for T-family instances

### Max Connections Reference

| RAM (GiB) | MySQL max_connections | PostgreSQL max_connections |
|-----------|----------------------|--------------------------|
| 1 | 66 | 112 |
| 2 | 150 | 225 |
| 4 | 312 | 450 |
| 8 | 640 | 900 |
| 16 | 1300 | 1800 |
| 32 | 2600 | 3600 |
| 64 | 5000 | 5000 |

Formula: MySQL ≈ RAM_bytes / 12582880, PostgreSQL ≈ RAM_bytes / 9531392

---

## Step 2: CloudWatch Metrics

### Core Metrics (always collect)

| Metric | Namespace | Dimension | Statistics | Purpose |
|--------|-----------|-----------|------------|---------|
| CPUUtilization | AWS/RDS | DBInstanceIdentifier | Average, Maximum | CPU usage pattern |
| DatabaseConnections | AWS/RDS | DBInstanceIdentifier | Average, Maximum | Activity indicator |
| FreeableMemory | AWS/RDS | DBInstanceIdentifier | Average, Minimum | Memory pressure |
| ReadIOPS | AWS/RDS | DBInstanceIdentifier | Average | IO read pattern |
| WriteIOPS | AWS/RDS | DBInstanceIdentifier | Average | IO write pattern |
| FreeStorageSpace | AWS/RDS | DBInstanceIdentifier | Average, Minimum | Storage utilization |

### Conditional Metrics

| Metric | When to Collect | Purpose |
|--------|----------------|---------|
| BurstBalance | T-family instances | CPU credit health |
| ReadLatency | io1/io2 storage | IO performance |
| WriteLatency | io1/io2 storage | IO performance |
| DiskQueueDepth | High IO workloads | IO saturation |
| NetworkReceiveThroughput | Large instances | Network utilization |
| NetworkTransmitThroughput | Large instances | Network utilization |

### Aurora-Specific Metrics

| Metric | Notes |
|--------|-------|
| ServerlessDatabaseCapacity | Aurora Serverless v2 current ACU |
| ACUUtilization | Aurora Serverless v2 ACU usage % |
| VolumeBytesUsed | Replaces FreeStorageSpace (Aurora storage auto-scales) |
| BufferCacheHitRatio | Cache efficiency |

**Aurora note:** Aurora instances do NOT have FreeStorageSpace. Use VolumeBytesUsed instead.
Aurora storage auto-scales, so storage over-provisioning is not applicable.

### Metric Collection via Script

**Do NOT call CloudWatch APIs manually.** Use `scripts/collect_rds_metrics.py` which:
- Fetches all core metrics in 1-minute granularity via MCP `call_aws`
- Batches by day to stay under CloudWatch's 1440 datapoint limit
- Aggregates locally and outputs compact JSON summary

**Usage:**
```bash
<skill-dir>/rightsizing-advisor/.venv/bin/python \
  <skill-dir>/rightsizing-advisor/scripts/collect_rds_metrics.py \
  --instances '<id or JSON array>' \
  --region <region> \
  --days <7|14|30> \
  --role-arn <from config.yaml> \
  --engine <engine from describe-db-instances, e.g. aurora-mysql, mysql, postgres> \
  --total-memory-gib <ram from instance class table above> \
  --allocated-storage-gb <storage GB, omit for Aurora> \
  --mcp-url '<from mcp.json>' \
  --mcp-headers '<from mcp.json>'
```

**Notes:**
- `--engine`: When set to `aurora-mysql` or `aurora-postgresql`, automatically skips
  FreeStorageSpace (Aurora storage auto-scales). Replaces the old `--is-aurora` flag.
- `--allocated-storage-gb`: Omit for Aurora instances (storage is cluster-level).
- `--mcp-headers`: Optional. Omit if MCP server has no auth.

**Script output fields and how to interpret them:**

| Field | Source | How to Use |
|-------|--------|------------|
| `metrics.CPUUtilization.avg` | CloudWatch Average | Overall CPU load. < 20% = over-provisioned, 40-80% = well-sized |
| `metrics.CPUUtilization.max` | CloudWatch Maximum | Peak CPU burst. If max > 50%, do NOT downsize based on low avg alone |
| `metrics.DatabaseConnections.avg/max` | CloudWatch | Activity level. max=0 over 7+ days = likely idle |
| `metrics.FreeableMemory.avg/min` | CloudWatch (bytes) | Memory pressure. Script converts to GiB in `memory` field |
| `metrics.ReadIOPS/WriteIOPS.avg` | CloudWatch | IO load. Compare against storage type max IOPS |
| `metrics.FreeStorageSpace.avg` | CloudWatch (bytes) | Script converts to utilization % in `storage` field |
| `metrics.*.weekday_avg/weekend_avg` | Computed | Only shown when weekday ≠ weekend. Large gap = scheduling opportunity |
| `peak_analysis.pattern` | Computed from hourly CPU + connections | `steady_state` = flat, `variable` = clear peak/off-peak hours, `spiky` = high variance but no clear hourly pattern |
| `peak_analysis.cv` | Coefficient of variation (std/mean) | Measures variability. < 0.15 = steady, > 0.3 = highly variable |
| `peak_analysis.peak_cpu_avg` | Computed | Only present when pattern=variable. Avg CPU during peak hours |
| `peak_analysis.offpeak_cpu_avg` | Computed | Only present when pattern=variable. Avg CPU during off-peak |
| `idle_detection.is_idle` | Computed | True if max CPU < 5% AND max connections = 0 AND avg IOPS < 1 (aligned with AWS Compute Optimizer) |
| `idle_detection.avg_total_iops` | Computed (ReadIOPS + WriteIOPS) | Combined avg IOPS. Used in idle check. > 0 with 0 connections = background activity |
| `spike_warning` | Computed | Present when CPU max > 3× avg. Means short bursts exist — do NOT downsize based on avg alone |
| `spike_warning.ratio` | cpu_max / cpu_avg | Higher ratio = more spiky. > 5 = very bursty workload |
| `memory.total_gib` | From --total-memory-gib param | Total instance RAM |
| `memory.used_avg_gib` | Computed from avg FreeableMemory | Average memory used |
| `memory.used_peak_gib` | Computed from min FreeableMemory | Peak memory used (tightest moment) |
| `memory.pct` | Computed from avg FreeableMemory | Average memory utilization % |
| `memory.peak_pct` | Computed from min FreeableMemory | Peak memory utilization % — use this to decide if downsizing is safe |
| `storage.pct` | Computed | Storage utilization %. < 30% = over-provisioned (but RDS storage can't shrink) |
| `waste_ratio_pct` | Computed | Overall waste %. For steady_state: based on max(CPU avg, memory avg). For variable: based on off-peak CPU and peak duration |
| `cpu_hourly_profile` | Computed | Only present when pattern=variable. 24h CPU averages for scheduling decisions |

**Critical interpretation rules:**

- `waste_ratio_pct` is based on the higher of CPU avg and memory utilization for steady_state
  instances. For variable instances, it's based on off-peak CPU and peak duration.
- Always check `memory.peak_pct` before recommending downsizing. If peak memory > 70%,
  the instance is memory-bound and needs that RAM even if CPU is low.
- `idle_detection.is_idle` is conservative (requires BOTH low CPU and low connections).
  An instance with 0 connections but 7% CPU (like Aurora background tasks) is NOT flagged idle.

---

## Step 3-4: RDS-Specific Analysis Notes

### Aurora Cluster Analysis

Aurora instances belong to clusters. Analyze them as a group, not individually.

**Step 1: Identify cluster topology**
```
call_aws("aws rds describe-db-clusters --no-paginate --region <region>", role_arn=...)
```
From `DBClusterMembers`, identify:
- Writer instance (`IsClusterWriter: true`) — handles all writes
- Reader instance(s) (`IsClusterWriter: false`) — handle read replicas

**Step 2: Analyze by role**

| Role | Key Metrics | Downsize Signal | Action |
|------|------------|-----------------|--------|
| Writer | CPU avg/max, WriteIOPS, Connections | CPU avg < 20%, max < 50% | Downsize instance class |
| Reader | CPU avg/max, ReadIOPS, Connections | CPU avg < 10%, connections near 0 | Remove reader (reduce replica count) |
| All members | Same low utilization | Entire cluster idle | Consider Aurora Serverless v2 |

**Step 3: Storage is cluster-level**
- Aurora storage auto-scales and is shared across all instances in the cluster
- Do NOT recommend storage changes (no gp2/gp3/io1 — Aurora has its own storage layer)
- `AllocatedStorage` in describe-db-instances is meaningless for Aurora
- Use `VolumeBytesUsed` from CloudWatch (cluster-level metric) if storage cost is a concern

**Step 4: Cluster-level recommendations**
- If all readers are idle → reduce reader count (save per-instance cost)
- If writer + readers all < 20% CPU → downsize all members, or migrate to Serverless v2
- If only writer is busy, readers idle → readers are over-provisioned or unnecessary
- Always recommend changes to all members of a cluster together (mixed sizes cause issues)

### Activity Metric

For RDS, the **activity metric** used in peak/off-peak classification is `DatabaseConnections`.
The script uses this automatically in idle detection.

### Memory & Storage

The script computes memory and storage utilization automatically when
`--total-memory-gib` and `--allocated-storage-gb` are provided.
Results appear in `memory.pct` and `storage.pct` fields.

Not applicable for Aurora storage (auto-scales) — use `--engine aurora-mysql` or `--engine aurora-postgresql`.

### IOPS Utilization

Approximate max IOPS by storage type (for manual reference):
- gp2: 3 × AllocatedStorage (min 100, max 16000)
- gp3: baseline 3000, configurable up to 16000
- io1/io2: provisioned value

Compare `metrics.ReadIOPS.avg + metrics.WriteIOPS.avg` against max IOPS.

---

## Step 5: RDS Optimization Paths

### Path 1: Downsize Instance Class

**When:** Peak CPU < 40%, memory utilization < 50%

**Sizing rule:**
- Peak CPU < 20% AND memory util < 40% → drop 2 sizes (e.g., r5.2xlarge → r5.large)
- Peak CPU 20-40% → drop 1 size (e.g., r5.xlarge → r5.large)

**Memory safety check (MANDATORY before any downsize):**

Use `memory.peak_pct` from script output:
```
IF memory.peak_pct > 70%:
    → Do NOT downsize (memory-bound workload)
IF target_class memory < memory.used_peak_gib / 0.7:
    → Do NOT downsize to this class (insufficient headroom)
```

**How:**
```bash
aws rds modify-db-instance \
  --db-instance-identifier <id> \
  --db-instance-class <new-class> \
  --apply-immediately \
  --region <region>
```

**Risk:** Brief downtime (5-15 min). Multi-AZ has shorter downtime via failover.

### Path 2: Graviton Migration

**When:** Running x86 instances (m5, r5, m6i, r6i families)

**Savings:** ~20% cost reduction for equivalent performance

**Compatibility:**
- MySQL 8.0+: ✅
- PostgreSQL 13+: ✅
- MariaDB 10.6+: ✅
- Oracle, SQL Server: ❌ Not supported

**Migration:** Modify instance class (e.g., r5.xlarge → r7g.xlarge). Brief downtime.

**Graviton generation preference:** r7g > r6g (newer = better price-performance)

### Path 3: Aurora Serverless v2

**When:** High peak/off-peak variance (peak CPU > 50%, off-peak CPU < 10%)

**How it works:**
- Scales between min and max ACU (1 ACU ≈ 2 GiB RAM)
- Scales in 0.5 ACU increments, responds in seconds

**Best for:** Spiky workloads, dev/test, clear day/night patterns

**Not suitable for:**
- Steady high-load (provisioned is cheaper)
- Non-Aurora engines (must migrate to Aurora first)

### Path 4: Storage Optimization

**gp2 → gp3:**
- ~20% cheaper per GB
- gp3 baseline: 3000 IOPS, 125 MiB/s (included)
- gp2 baseline: 3 IOPS/GB (need 1000 GB for 3000 IOPS)
- Online migration, no downtime

```bash
aws rds modify-db-instance \
  --db-instance-identifier <id> \
  --storage-type gp3 \
  --apply-immediately \
  --region <region>
```

**Reduce provisioned IOPS (io1/io2):**
- When avg IOPS utilization < 30% of provisioned
- Or switch to gp3 if provisioned IOPS < 16000

**Storage can NOT shrink:** RDS storage only increases. Over-provisioned storage
can only be fixed by migrating to a new instance with less storage.

### Path 5: Reserved Instances

**When:** Steady-state workload, running > 30 days, no planned changes

**Savings:** 1yr ~30%, 3yr ~50%

**Check current RI coverage:**
```bash
aws rds describe-reserved-db-instances --no-paginate --region <region>
```

### Path 6: Scheduled Scaling

**When:** Clear time-based pattern, can't use Serverless

**Implementation:** EventBridge + Lambda to modify instance class on schedule
(e.g., scale up at 8am, down at 8pm)

**Caveat:** Each modification causes brief downtime.

### Path 7: Stop Idle Instances

**When:** `idle_detection.is_idle = true`

```bash
aws rds stop-db-instance --db-instance-identifier <id> --region <region>
```

**Note:** RDS auto-restarts stopped instances after 7 days. For permanent removal,
create a final snapshot and delete the instance.

### Path 8: Extended Support Cost Avoidance

**When:** Engine version is past end of standard support (e.g., MySQL 5.7, PostgreSQL 11)

RDS Extended Support charges extra per-vCPU-hour for engines past their community
end-of-life date. This is a hidden cost that increases over time.

**How to detect:** From Step 1's `describe-db-instances` output, check:
- `EngineVersion` — the exact version (e.g., `5.7.44`, `8.0.mysql_aurora.3.08.2`)
- `EngineLifecycleSupport` — if value is `open-source-rds-extended-support`, the instance
  is being charged Extended Support fees

**Action:**
1. Use `search_documentation` or `read_documentation` to look up the exact Extended Support
   timeline and charges for the detected engine version:
   - Search: "RDS Extended Support {engine} {version} end of standard support date"
   - Or read: `https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/extended-support.html`
2. Include in the report: current version, Extended Support status, end date, and
   recommended target version
3. Recommend upgrading to a supported major version with specific upgrade path:
   - MySQL 5.7 → 8.0 (test compatibility, check deprecated features)
   - PostgreSQL 11 → 16 (check extension compatibility)
   - Aurora MySQL 2 (5.7) → Aurora MySQL 3 (8.0)
4. Note: upgrading also unlocks Graviton support and newer instance types, compounding savings

### Path 9: Multi-AZ Optimization

**When:** Non-production instances running Multi-AZ (`MultiAZ: true`)

Multi-AZ doubles the instance cost. Dev/test/staging environments rarely need it.

**Action:** Disable Multi-AZ for non-production workloads:
```bash
aws rds modify-db-instance \
  --db-instance-identifier <id> \
  --no-multi-az \
  --apply-immediately \
  --region <region>
```

**Savings:** ~50% of instance cost.

### Path 10: Read Replica Cleanup

**When:** Read replicas with near-zero connections and low ReadIOPS

**How to detect:** Check `ReadReplicaDBInstanceIdentifiers` from describe-db-instances.
For each replica, check if connections and ReadIOPS are near zero.

**Action:** Delete unused read replicas. Each replica costs the same as a full instance.

### Path 11: Instance Generation Upgrade

**When:** Running older generation instances (m5, r5, m6i) even if already on Graviton (r6g)

Newer generations (r7g, m7g) offer better price-performance than older ones,
independent of the x86→Graviton migration.

**Action:** Upgrade to latest available generation. Check compatibility first.

---

## Thresholds

| Metric | Idle | Under-utilized | Well-sized | Over-utilized |
|--------|------|---------------|------------|---------------|
| Peak CPU | < 5% | < 40% | 40-80% | > 80% |
| Off-Peak CPU | < 2% | < 10% | 10-30% | > 30% |
| Memory Util | < 10% | < 40% | 40-80% | > 80% |
| Connections (max) | 0 | < 20% of max | 20-70% of max | > 70% of max |
| Avg IOPS (R+W) | < 1 | < 30% of max | 30-70% of max | > 70% |
| Storage Util | - | < 30% | 30-80% | > 80% |
| IOPS Util | < 5% | < 30% | 30-70% | > 70% |
| BurstBalance (T) | always 100% | > 80% | 30-80% | < 30% |

---

## Common Pitfalls

### ❌ Downsizing memory-bound workloads
CPU may be low but if FreeableMemory is also low, the instance needs that RAM.
Always check memory before recommending CPU-based downsizing.

### ❌ Ignoring T-family burst behavior
T3/T4g showing 60% CPU may be fine if BurstBalance > 30%.
But if BurstBalance hits 0, it's under-provisioned — consider M/R family.

### ❌ Recommending Aurora Serverless for non-Aurora engines
Aurora Serverless v2 only works with Aurora MySQL and Aurora PostgreSQL.
RDS MySQL/PostgreSQL must migrate to Aurora first — separate project.

### ❌ Forgetting Multi-AZ cost
Multi-AZ instances cost ~2x. Double the per-instance savings for Multi-AZ.

### ❌ Storage can't shrink
RDS storage can only increase. Don't recommend "reduce storage."

### ❌ Aurora has no FreeStorageSpace
Aurora storage auto-scales. Use VolumeBytesUsed instead.
Do NOT recommend gp2/gp3/io1/io2 changes for Aurora — it has its own storage layer.
`AllocatedStorage` shown in describe-db-instances is always 1 for Aurora and is meaningless.

### ❌ Analyzing Aurora instances individually
Aurora instances in the same cluster share storage and replication.
Always group by `DBClusterIdentifier`, distinguish writer vs reader roles,
and recommend changes at the cluster level.

---

## Documentation References

| Topic | URL |
|-------|-----|
| RDS instance classes | https://docs.amazonaws.cn/en_us/AmazonRDS/latest/UserGuide/Concepts.DBInstanceClass.html |
| Modify DB instance | https://docs.amazonaws.cn/en_us/AmazonRDS/latest/UserGuide/Overview.DBInstance.Modifying.html |
| RDS storage types | https://docs.amazonaws.cn/en_us/AmazonRDS/latest/UserGuide/CHAP_Storage.html |
| Aurora Serverless v2 | https://docs.amazonaws.cn/en_us/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.html |
| Reserved Instances | https://docs.amazonaws.cn/en_us/AmazonRDS/latest/UserGuide/USER_WorkingWithReservedDBInstances.html |
| CloudWatch RDS metrics | https://docs.amazonaws.cn/en_us/AmazonRDS/latest/UserGuide/monitoring-cloudwatch.html |
| RDS Extended Support | https://docs.amazonaws.cn/en_us/AmazonRDS/latest/UserGuide/extended-support.html |
| Extended Support charges | https://docs.amazonaws.cn/en_us/AmazonRDS/latest/UserGuide/extended-support-charges.html |
| Right sizing whitepaper | https://docs.aws.amazon.com/whitepapers/latest/cost-optimization-right-sizing/tips-for-right-sizing-your-workloads.html |
| Compute Optimizer for RDS | https://aws.amazon.com/blogs/database/how-to-optimize-amazon-rds-and-amazon-aurora-database-costs-performance-with-aws-compute-optimizer/ |
