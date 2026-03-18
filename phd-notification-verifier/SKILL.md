---
name: phd-verifier
description: Check and verify AWS Personal Health Dashboard EOL events. Use when: (1) Customer asks "check PHD" or "list EOL events", (2) Need to verify if EOL/deprecation events are resolved (RDS version, SageMaker platform, Lambda runtime, etc.), (3) Validate maintenance windows completed, (4) Check if retirement/certificate expiry issues addressed. Returns verification report with resolved/unresolved conclusions and confidence scores.
---

# PHD Notification Verifier

Check AWS Personal Health Dashboard (PHD) events and **verify if issues are resolved** by querying actual resource state.

## Core Workflow

**Default behavior: Always verify resources, not just list events**

```
1. Get PHD events (describe-events)
   ↓
2. Filter EOL events (PLANNED_LIFECYCLE_EVENT)
   ↓
3. Get event details (describe-event-details) ← EOL version info
   ↓
4. Get affected resources (describe-affected-entities)
   ↓
5. **Query resource state** (service-specific APIs)
   ↓
6. **Compare & conclude** (✅ Resolved / ❌ Not resolved)
```

**Why this matters:** PHD events persist even after issues are resolved. Verification determines if the underlying problem is actually fixed.

---

## Step-by-Step Guide

### Step 1: Get Scheduled Change Events

```bash
aws health describe-events \
  --filter eventTypeCategories=scheduledChange \
  --max-results 100 \
  --region cn-northwest-1
```

**Pagination:**
- Check `nextToken` in response
- Continue with `--next-token <token>` until all pages fetched

**Region:**
- China: `cn-northwest-1` or `cn-north-1`
- Global: `us-east-1`

---

### Step 2: Filter EOL Events (Client-Side)

From describe-events results, keep only EOL events:
```python
eol_events = [e for e in events if "PLANNED_LIFECYCLE_EVENT" in e["eventTypeCode"]]
```

**EOL event pattern:** `AWS_{SERVICE}_PLANNED_LIFECYCLE_EVENT`

**Non-EOL patterns (exclude):**
- `AWS_*_SCHEDULED_MAINTENANCE`
- `AWS_EC2_INSTANCE_RETIREMENT_SCHEDULED`

**Token savings:** ~45% by filtering before describe-event-details

---

### Step 3: Get Event Details (EOL Version Info)

**Critical:** This step provides EOL version/date information.

```bash
aws health describe-event-details \
  --event-arns <arn1> <arn2> ... \
  --region cn-northwest-1
```

**Batch processing:** Max 10 ARNs per call

**Returns:**
- `eventDescription.latestDescription` - Detailed text (EOL version/date)
- `eventMetadata` - Structured fields:
  - `EOL_VERSION` or `deprecated_versions` - What's being EOL'd
  - `EOL_DATE` - When it expires
  - `SUPPORTED_VERSION` - What to upgrade to

**Example:**
```json
{
  "eventMetadata": {
    "deprecated_versions": "notebook-al2-v1, notebook-al2-v2",
    "EOL_DATE": "2026-02-28"
  }
}
```

**Parse EOL versions from:**
1. `eventMetadata` fields (structured)
2. `latestDescription` text (if metadata missing)

---

### Step 4: Get Affected Resources

```bash
aws health describe-affected-entities \
  --filter eventArns=<arn> \
  --max-results 100 \
  --region cn-northwest-1
```

**Pagination:** A single event may affect hundreds of resources. Fetch all pages.

**Returns:** List of `entityValue` (ARNs or resource identifiers)

---

### Step 5: Query Resource State (Critical Step)

**For each affected resource, query its current state using service-specific APIs.**

See [VERIFICATION.md](references/VERIFICATION.md) for all supported services.

**Key principle:** Get FULL resource details (no `--query` filtering)

**Examples:**

**SageMaker Notebook:**
```bash
aws sagemaker describe-notebook-instance \
  --notebook-instance-name <name> \
  --region cn-north-1
```
→ Check `PlatformIdentifier` field

**RDS Instance:**
```bash
aws rds describe-db-instances \
  --db-instance-identifier <id> \
  --region cn-north-1
```
→ Check `EngineVersion` field

**Lambda Function:**
```bash
aws lambda get-function \
  --function-name <name> \
  --region cn-north-1
```
→ Check `Runtime` field

---

### Step 6: Compare & Conclude

**Verification logic:**

```python
# Extract current version from resource state
current_version = resource["PlatformIdentifier"]  # Example

# Parse EOL versions from event details (Step 3)
eol_versions = ["notebook-al2-v1", "notebook-al2-v2"]

# Compare
if current_version in eol_versions:
    conclusion = "❌ Not resolved"
    confidence = 100
elif resource_not_found:
    conclusion = "✅ Resolved (deleted/replaced)"
    confidence = 90
else:
    conclusion = "✅ Resolved (upgraded)"
    confidence = 95
```

**Confidence scores:**
- **95-100%**: Definitive evidence (version changed, resource deleted)
- **70-95%**: Strong indicators (last modified after EOL date)
- **50-70%**: Mixed signals (need human review)
- **<50%**: Cannot determine

**Always provide evidence:** Cite specific field values from API responses.

---

## Output Format

**Goal: Clear resolved/unresolved conclusions for each event**

```markdown
## PHD Verification Report - Account {account_id}

**Total EOL Events:** X
**Resolved:** Y
**Not Resolved:** Z

---

### ✅ Resolved: [Service] [Event Type]

**Event ARN:** [arn]
**EOL Date:** [date]
**EOL Versions:** [v1, v2]
**Affected Resources:** X resources

**Verification:**
- Resource: [name/ARN]
- Current State: [field]=[value] ✅
- Last Modified: [timestamp]
- Conclusion: ✅ **Resolved** (Confidence: 95%)

**Evidence:**
```json
{
  "PlatformIdentifier": "notebook-al2-v3",
  "LastModifiedTime": "2026-03-09T20:44:56Z"
}
```

---

### ❌ Not Resolved: [Service] [Event Type]

**Event ARN:** [arn]
**EOL Date:** [date]
**EOL Versions:** [v1, v2]
**Affected Resources:** X resources

**Verification:**
- Resource: [name/ARN]
- Current State: [field]=[value] ❌
- Issue: Still running EOL version
- Conclusion: ❌ **Not Resolved** (Confidence: 100%)

**Evidence:**
```json
{
  "Runtime": "python3.7",
  "LastModifiedTime": "2023-05-10T12:00:00Z"
}
```

**Action Required:**
[Specific remediation steps]

---

### 🔵 Cannot Verify: [Service] [Event Type]

**Reason:** [AccessDenied / ResourceNotFound / UnsupportedService]
**Suggestion:** [Manual check / Grant permissions / Use AWS Console]
```

---

## Decision Tree: When to Verify

**Default: Always verify unless:**

1. **No Business/Enterprise Support** → Cannot call Health API
2. **Event is not PLANNED_LIFECYCLE_EVENT** → Not an EOL event
3. **Service not supported** (see VERIFICATION.md) → Mark as "Cannot verify"

**If user says "list" or "summary":** Still verify, but group by resolved/unresolved.

**If user says "verify":** Same workflow, provide detailed evidence.

---

## Best Practices

### 1. Always Query Resource State
- **Don't assume** events are unresolved
- **Don't stop** at listing events
- **Always** query actual resource state (Step 5)

### 2. Parse EOL Versions Carefully
- Check `eventMetadata` first (structured)
- Fallback to `latestDescription` text parsing
- Extract all EOL versions (may be multiple)

### 3. Provide Clear Evidence
- Quote specific field values from API responses
- Include timestamps (proves when upgrade happened)
- Show both expected (EOL) and actual (current) values

### 4. Handle Edge Cases
- Resource deleted → ✅ Resolved (confidence 90%)
- Resource not found → Could be resolved or permission issue
- Multiple resources → Verify each one
- Mixed states → Report percentage (e.g., "3/5 resolved")

---

## Common Pitfalls to Avoid

### ❌ Listing events without verification
**Bad:**
> "You have 5 SageMaker EOL events. You should upgrade."

**Good:**
> "5 SageMaker EOL events found. Verified resource `luchen`: ✅ Already upgraded to `notebook-al2-v3` on 2026-03-09. No action needed (Confidence: 100%)."

### ❌ Missing EOL version info
**Bad:**
> "Resource version is `notebook-al2-v3`. Status unknown."

**Good:**
> "EOL versions: `notebook-al2-v1`, `notebook-al2-v2`. Current: `notebook-al2-v3`. ✅ Resolved (Confidence: 95%)."

### ❌ No evidence
**Bad:**
> "Resource appears to be upgraded."

**Good:**
> "Evidence: `PlatformIdentifier=notebook-al2-v3`, `LastModifiedTime=2026-03-09T20:44:56Z`"

---

## Prerequisites

### Tools Required

**Primary: `call_aws` tool (MCP Hub)**

**Fallback: AWS CLI**

### AWS Health API Requirements

**⚠️ Requires Business or Enterprise Support**

Without support plan → Suggest EventBridge rules

---

## Cross-Account Configuration

**MCP Hub:**
```
role_arn: "arn:aws-cn:iam::123456789012:role/RoleName"
```

**AWS CLI:**
```ini
[profile account-a]
role_arn = arn:aws-cn:iam::123456789012:role/RoleName
source_profile = default
```

---

## Supported Services

See [VERIFICATION.md](references/VERIFICATION.md) for:
- Service-by-service verification commands
- Field names to check
- EOL version patterns
- Common edge cases

**Currently supported:**
- SageMaker (Notebook, Studio, Processing)
- RDS (MySQL, PostgreSQL, MariaDB)
- Lambda (Runtimes)
- ElastiCache (Redis, Memcached)
- OpenSearch
- MSK (Kafka)
- ECS (Fargate platform)
- EKS (Kubernetes version)
- EC2 (Instance retirement, certificate expiry)
- ELB (Certificate expiry)

---

## Error Handling

### SubscriptionRequiredException
→ Account lacks Business/Enterprise support. Cannot proceed.

### AccessDeniedException
→ Missing IAM permissions. Suggest granting `health:*` or checking role trust policy.

### ResourceNotFoundException
→ Resource deleted or ARN incorrect. Mark as ✅ Resolved (90% confidence).

### ThrottlingException
→ Too many API calls. Implement backoff and retry.

---

## Important Notes

- PHD events **persist** even after issues are resolved
- Goal: Verify if **underlying issue** is fixed, not just list events
- Always get full API responses (no `--query` filtering)
- Provide specific evidence from API fields
- Report confidence scores for all conclusions
