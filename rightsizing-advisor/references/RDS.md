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
| Version | EngineVersion | |
| Multi-AZ | MultiAZ | true = 2x cost |
| Storage Type | StorageType | gp2/gp3/io1/io2/aurora |
| Storage Size | AllocatedStorage | GB (not applicable for Aurora) |
| Status | DBInstanceStatus | Skip if not "available" |
| Created | InstanceCreateTime | For RI eligibility check |

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
  --total-memory-gib <ram from instance class table above> \
  --allocated-storage-gb <storage GB, omit for Aurora> \
  --is-aurora \
  --mcp-url '<from mcp.json>' \
  --mcp-headers '<from mcp.json>'
```

**Script output fields used for analysis:**

| Field | What It Tells You |
|-------|-------------------|
| `metrics.CPUUtilization.overall.avg/max` | Overall CPU usage |
| `metrics.CPUUtilization.hourly_profile` | 24h pattern (peak detection) |
| `metrics.*.weekday_weekend` | Weekday vs weekend comparison |
| `peak_analysis.pattern` | "steady_state" or "variable" |
| `peak_analysis.peak_cpu_avg / offpeak_cpu_avg` | Peak vs off-peak CPU |
| `idle_detection.is_idle` | True if max CPU < 5% and max connections < 2 |
| `memory.pct` | Memory utilization % (if --total-memory-gib provided) |
| `storage.pct` | Storage utilization % (if --allocated-storage-gb provided) |
| `waste_ratio_pct` | Overall capacity waste % |

---

## Step 3-4: RDS-Specific Analysis Notes

### Activity Metric

For RDS, the **activity metric** used in peak/off-peak classification is `DatabaseConnections`.
The script uses this automatically in idle detection.

### Memory & Storage

The script computes memory and storage utilization automatically when
`--total-memory-gib` and `--allocated-storage-gb` are provided.
Results appear in `memory.pct` and `storage.pct` fields.

Not applicable for Aurora storage (auto-scales) — use `--is-aurora` flag.

### IOPS Utilization

Approximate max IOPS by storage type (for manual reference):
- gp2: 3 × AllocatedStorage (min 100, max 16000)
- gp3: baseline 3000, configurable up to 16000
- io1/io2: provisioned value

Compare `metrics.ReadIOPS.overall.avg + metrics.WriteIOPS.overall.avg` against max IOPS.

---

## Step 5: RDS Optimization Paths

### Path 1: Downsize Instance Class

**When:** Peak CPU < 40%, memory utilization < 50%

**Sizing rule:**
- Peak CPU < 20% AND memory util < 40% → drop 2 sizes (e.g., r5.2xlarge → r5.large)
- Peak CPU 20-40% → drop 1 size (e.g., r5.xlarge → r5.large)

**Memory safety check (MANDATORY before any downsize):**
```
memory_used = total_memory - avg_FreeableMemory
target_memory = specs[target_class].memory_gib
IF memory_used > target_memory × 0.7:
    → Do NOT downsize (memory-bound workload)
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

**When:** Idle (CPU < 5%, connections < 2) for > 90% of lookback

```bash
aws rds stop-db-instance --db-instance-identifier <id> --region <region>
```

**Note:** RDS auto-restarts stopped instances after 7 days.

---

## Thresholds

| Metric | Idle | Under-utilized | Well-sized | Over-utilized |
|--------|------|---------------|------------|---------------|
| Peak CPU | < 5% | < 40% | 40-80% | > 80% |
| Off-Peak CPU | < 2% | < 10% | 10-30% | > 30% |
| Memory Util | < 10% | < 40% | 40-80% | > 80% |
| Connections (max) | < 2 | < 20% of max | 20-70% of max | > 70% of max |
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

---

## Documentation References

| Topic | URL |
|-------|-----|
| RDS instance classes | https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.DBInstanceClass.html |
| Modify DB instance | https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Overview.DBInstance.Modifying.html |
| RDS storage types | https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Storage.html |
| Aurora Serverless v2 | https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.html |
| RDS Graviton | https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.DBInstanceClass.html#Concepts.DBInstanceClass.Support |
| Reserved Instances | https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithReservedDBInstances.html |
| CloudWatch RDS metrics | https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/monitoring-cloudwatch.html |
| Right sizing whitepaper | https://docs.aws.amazon.com/whitepapers/latest/cost-optimization-right-sizing/tips-for-right-sizing-your-workloads.html |
| Compute Optimizer for RDS | https://aws.amazon.com/blogs/database/how-to-optimize-amazon-rds-and-amazon-aurora-database-costs-performance-with-aws-compute-optimizer/ |
