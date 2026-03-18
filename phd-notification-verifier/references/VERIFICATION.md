# PHD Event Verification Reference

Service-specific verification commands and patterns for all AWS services.

## Important: Pagination

**All Health API calls support pagination:**

```bash
# describe-events
aws health describe-events --filter eventStatusCodes=open --max-results 100 --region cn-northwest-1

# If response contains nextToken, continue:
aws health describe-events --filter eventStatusCodes=open --max-results 100 --next-token <token> --region cn-northwest-1

# describe-affected-entities
aws health describe-affected-entities --filter eventArns=<arn> --max-results 100 --region cn-northwest-1

# Continue with nextToken if present
aws health describe-affected-entities --filter eventArns=<arn> --max-results 100 --next-token <token> --region cn-northwest-1
```

**Why pagination matters:**
- Customers may have hundreds of PHD events
- A single event may affect hundreds of resources
- Without pagination, you'll miss events/resources
- **Always check for `nextToken` in response**

## Workflow

### 1. Get Events List
```bash
aws health describe-events --filter eventStatusCodes=open --max-results 100 --region cn-northwest-1
```

### 2. Get Event Details (EOL Info)
```bash
aws health describe-event-details --event-arns <arn> --region cn-northwest-1
```

**Returns:**
- `eventDescription.latestDescription` - Detailed text with EOL version/date
- `eventMetadata` - Structured key-value pairs (may contain EOL_VERSION, EOL_DATE)

**Example output:**
```json
{
  "successfulSet": [{
    "event": { ... },
    "eventDescription": {
      "latestDescription": "Amazon RDS will end support for MySQL 5.7 on 2024-02-29. Upgrade to MySQL 8.0 or higher."
    },
    "eventMetadata": {
      "EOL_DATE": "2024-02-29",
      "EOL_VERSION": "5.7",
      "SUPPORTED_VERSIONS": "8.0, 8.3"
    }
  }]
}
```

### 3. Get Affected Resources
```bash
aws health describe-affected-entities --filter eventArns=<arn> --max-results 100 --region cn-northwest-1
```

### 4. Verify Current Resource State
Use service-specific commands (see below) to check if resource has been upgraded/resolved.

## Table of Contents

- [SageMaker EOL Events](#sagemaker-eol-events)
- [RDS EOL Events](#rds-eol-events)
- [Lambda Runtime Deprecation](#lambda-runtime-deprecation)
- [MSK EOL Events](#msk-eol-events)
- [ElastiCache EOL Events](#elasticache-eol-events)
- [OpenSearch EOL Events](#opensearch-eol-events)
- [ECS Platform EOL](#ecs-platform-eol)
- [EKS Version EOL](#eks-version-eol)
- [EC2 Retirement](#ec2-retirement)
- [ELB Certificate Expiry](#elb-certificate-expiry)

---

## SageMaker EOL Events

**Event Type:** `AWS_SAGEMAKER_PLANNED_LIFECYCLE_EVENT`

**Example:** JupyterLab 1/3 EOL (2025-06-30)

**Get affected resource:**
```
aws health describe-affected-entities --event-arn <arn> --region cn-northwest-1
→ arn:aws-cn:sagemaker:cn-north-1:123456789012:notebook-instance/my-notebook
```

**Check current state:**
```
aws sagemaker describe-notebook-instance --notebook-instance-name my-notebook --region cn-north-1
```

**Key field:** `PlatformIdentifier`

**EOL values:**
- `notebook-al2-v1` (JupyterLab 1)
- `notebook-al2-v2` (JupyterLab 3)

**Supported value:**
- `notebook-al2-v3` (JupyterLab 4)

**Verification:**
```
IF PlatformIdentifier == "notebook-al2-v3":
    ✅ Upgraded (95% confidence)
ELIF PlatformIdentifier IN ["notebook-al2-v1", "notebook-al2-v2"]:
    ❌ Not upgraded
ELIF instance_not_found:
    ✅ Deleted/replaced (90% confidence)
```

---

## RDS EOL Events

**Event Type:** `AWS_RDS_PLANNED_LIFECYCLE_EVENT`

**Example:** MySQL 5.7 EOL, PostgreSQL 11 EOL

**Get affected resource:**
```
aws health describe-affected-entities --event-arn <arn> --region cn-northwest-1
→ db-instance-id
```

**Check current state:**
```
aws rds describe-db-instances --db-instance-identifier <id> --region cn-northwest-1
```

**Key fields:**
- `EngineVersion`
- `DBInstanceStatus`
- `PendingModifiedValues`

**Verification:**
```
IF EngineVersion NOT IN eol_versions:
    ✅ Upgraded (95% confidence)
ELIF EngineVersion IN eol_versions:
    ❌ Not upgraded
```

---

## Lambda Runtime Deprecation

**Event Type:** `AWS_LAMBDA_RUNTIME_DEPRECATION`

**Example:** python3.8, nodejs14.x EOL

**Get affected resource:**
```
aws health describe-affected-entities --event-arn <arn> --region cn-northwest-1
→ function-name
```

**Check current state:**
```
aws lambda get-function --function-name <name> --region cn-northwest-1
```

**Key fields:**
- `Runtime`
- `LastModified`
- `State`

**EOL runtimes:**
- python3.6, python3.7, python3.8
- nodejs12.x, nodejs14.x
- dotnetcore2.1, dotnetcore3.1
- ruby2.5, ruby2.7

**Verification:**
```
IF Runtime NOT IN eol_runtimes:
    ✅ Upgraded (95% confidence)
ELIF Runtime IN eol_runtimes AND LastModified > event_start:
    ⚠️ Modified but still EOL (70% confidence - may have other changes)
ELIF Runtime IN eol_runtimes:
    ❌ Not upgraded
```

---

## MSK EOL Events

**Event Type:** `AWS_MSK_PLANNED_LIFECYCLE_EVENT`

**Get affected resource:**
```
aws health describe-affected-entities --event-arn <arn> --region cn-northwest-1
→ cluster-arn
```

**Check current state:**
```
aws kafka describe-cluster-v2 --cluster-arn <arn> --region cn-northwest-1
```

**Key field:** `CurrentVersion` (in ClusterInfo.CurrentVersion)

**Verification:**
```
IF CurrentVersion NOT IN eol_versions:
    ✅ Upgraded (95% confidence)
```

---

## ElastiCache EOL Events

**Event Type:** `AWS_ELASTICACHE_PLANNED_LIFECYCLE_EVENT`

**Get affected resource:**
```
aws health describe-affected-entities --event-arn <arn> --region cn-northwest-1
→ cache-cluster-id
```

**Check current state:**
```
aws elasticache describe-cache-clusters --cache-cluster-id <id> --region cn-northwest-1
```

**Key field:** `EngineVersion`

**Verification:**
```
IF EngineVersion NOT IN eol_versions:
    ✅ Upgraded (95% confidence)
```

---

## OpenSearch EOL Events

**Event Type:** `AWS_OPENSEARCH_PLANNED_LIFECYCLE_EVENT`

**Get affected resource:**
```
aws health describe-affected-entities --event-arn <arn> --region cn-northwest-1
→ domain-name
```

**Check current state:**
```
aws opensearch describe-domain --domain-name <name> --region cn-northwest-1
```

**Key field:** `EngineVersion` (in DomainStatus.EngineVersion)

**Verification:**
```
IF EngineVersion NOT IN eol_versions:
    ✅ Upgraded (95% confidence)
```

---

## ECS Platform EOL

**Event Type:** `AWS_ECS_PLANNED_LIFECYCLE_EVENT`

**Get affected resource:**
```
aws health describe-affected-entities --event-arn <arn> --region cn-northwest-1
→ service-arn
```

**Check current state:**
```
aws ecs describe-services --services <arn> --cluster <cluster> --region cn-northwest-1
```

**Key field:** `PlatformVersion` (in Services[].PlatformVersion)

**Verification:**
```
IF PlatformVersion NOT IN eol_versions:
    ✅ Upgraded (95% confidence)
```

---

## EKS Version EOL

**Event Type:** `AWS_EKS_PLANNED_LIFECYCLE_EVENT`

**Get affected resource:**
```
aws health describe-affected-entities --event-arn <arn> --region cn-northwest-1
→ cluster-name
```

**Check current state:**
```
aws eks describe-cluster --name <name> --region cn-northwest-1
```

**Key field:** `Version` (in Cluster.Version)

**Verification:**
```
IF Version NOT IN eol_versions:
    ✅ Upgraded (95% confidence)
```

---

## EC2 Retirement

**Event Type:** `AWS_EC2_INSTANCE_RETIREMENT_SCHEDULED`

**Get affected resource:**
```
aws health describe-affected-entities --event-arn <arn> --region cn-northwest-1
→ i-xxx
```

**Check current state:**
```
aws ec2 describe-instances --instance-ids i-xxx --region cn-northwest-1
```

**Key fields:**
- `State.Name`
- `LaunchTime`

**Verification:**
```
IF State.Name IN ["stopped", "terminated"]:
    ✅ Resolved (95% confidence)
ELIF instance_not_found:
    ✅ Deleted/replaced (90% confidence)
ELIF State.Name == "running" AND LaunchTime > event_start:
    ✅ Replaced (85% confidence - new instance)
ELIF State.Name == "running":
    ❌ Not resolved
```

---

## ELB Certificate Expiry

**Event Type:** `AWS_ELB_SSL_CERTIFICATE_EXPIRING`

**Get affected resource:**
```
aws health describe-affected-entities --event-arn <arn> --region cn-northwest-1
→ load-balancer-arn
```

**Check current state:**
```
aws elbv2 describe-listeners --load-balancer-arn <arn> --region cn-northwest-1
```

Then check certificates:
```
aws elbv2 describe-listener-certificates --listener-arn <arn> --region cn-northwest-1
```

**Key fields:**
- Certificate ARN
- NotAfter date (expiry)

**Verification:**
```
IF certificate_arn_changed:
    ✅ Renewed (95% confidence)
ELIF days_until_expiry > 30:
    ✅ Sufficient time remaining (90% confidence)
ELIF days_until_expiry < 7:
    ❌ Urgent - needs renewal
```

---

## General Patterns

### Timeline-Based Evidence

**Strong indicator:** Resource modified after event start date

```
IF LastModifiedTime > event.startTime:
    confidence += 30%
```

### Resource Not Found

```
IF resource_not_found:
    ✅ Likely deleted/replaced (90% confidence)
    Note: Verify with user if intentional
```

### Multiple Affected Resources

```
FOR each resource:
    verify individually
AGGREGATE confidence = average(all_confidences)
```

---

## Common Mistakes

### ❌ Filtering API Fields

Don't use `--query` to filter fields:
```bash
# Wrong
aws sagemaker describe-notebook-instance --notebook-instance-name x --query 'NotebookInstanceStatus'

# Right
aws sagemaker describe-notebook-instance --notebook-instance-name x
```

**Reason:** Important fields like `PlatformIdentifier` may be filtered out.

### ❌ Wrong Region

Health API is global but requires region parameter:
- China: `cn-northwest-1` or `cn-north-1`
- Global: `us-east-1`

### ❌ Incomplete Evidence

Always cite specific field values:
```
❌ "Instance has been upgraded"
✅ "PlatformIdentifier: notebook-al2-v3 (upgraded from v1/v2)"
```
