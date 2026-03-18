---
name: phd-verifier
description: Check and verify AWS Personal Health Dashboard EOL events. Use when: (1) Customer asks "check PHD" or "list EOL events", (2) Need to verify if EOL/deprecation events are resolved (RDS version, SageMaker platform, Lambda runtime, etc.), (3) Validate maintenance windows completed, (4) Check if retirement/certificate expiry issues addressed. Returns verification report with resolved/unresolved conclusions and confidence scores.
---

# PHD Notification Verifier

Check AWS Personal Health Dashboard (PHD) events and verify if issues are resolved by querying actual resource state.

## Quick Start

1. Read config.yaml to get target account's role_arn
2. Execute 6-step verification workflow (see references/VERIFICATION.md)
3. Generate report using templates (see references/OUTPUT-FORMATS.md)

## Configuration

**CRITICAL: Always load config.yaml first**

config.yaml structure:

    cross_account:
      accounts:
        "123456789012":
          role_arn: "arn:aws-cn:iam::123456789012:role/RoleName"
          regions: ["cn-northwest-1"]

Workflow:
1. Read config.yaml
2. Find target account ID (from user request)
3. Extract role_arn
4. Use role_arn in ALL call_aws tool calls

**Never hardcode role ARNs.**

## Core Workflow

### Step 1: Get PHD Events

```bash
aws health describe-events \
  --filter eventTypeCategories=scheduledChange \
  --max-results 100 \
  --region <region>
```

**Pagination:** Check `nextToken` in response. Continue with `--next-token <token>` until all pages fetched.

**Region:** 
- China: `cn-northwest-1` or `cn-north-1`
- Global: `us-east-1`

---

### Step 2: Filter EOL Events (Client-Side)

From describe-events results, keep only EOL events:

```python
eol_events = [e for e in events if "PLANNED_LIFECYCLE_EVENT" in e["eventTypeCode"]]
```

**EOL pattern:** `AWS_{SERVICE}_PLANNED_LIFECYCLE_EVENT`

**Non-EOL patterns (exclude):**
- `AWS_*_SCHEDULED_MAINTENANCE`
- `AWS_EC2_INSTANCE_RETIREMENT_SCHEDULED`

**Why filter:** Token savings ~45% (100 events → 40 EOL events)

---

### Step 3: Get Event Details (EOL Version Info)

**Critical step:** Provides EOL version/date information.

```bash
aws health describe-event-details \
  --event-arns <arn1> <arn2> ... (max 10 per call) \
  --region <region>
```

**Returns:**
- `eventDescription.latestDescription` - Detailed text (EOL version/date)
- `eventMetadata` - Structured fields:
  - `EOL_VERSION` or `deprecated_versions` - What's EOL
  - `EOL_DATE` - When it expires
  - `SUPPORTED_VERSIONS` - What to upgrade to

**Example:**
```json
{
  "eventMetadata": {
    "deprecated_versions": "notebook-al2-v1, notebook-al2-v2",
    "EOL_DATE": "2026-02-28"
  }
}
```

---

### Step 4: Get Affected Resources

```bash
aws health describe-affected-entities \
  --filter eventArns=<arn> \
  --max-results 100 \
  --region <region>
```

**Pagination:** A single event may affect hundreds of resources. Fetch all pages.

**Returns:** List of `entityValue` (ARNs or resource identifiers)

---

### Step 5: Query Resource State

**For each affected resource, query its current state.**

**Common services:**

**SageMaker Notebook:**
```bash
aws sagemaker describe-notebook-instance \
  --notebook-instance-name <name> \
  --region <region>
```
→ Check `PlatformIdentifier` field

**RDS Instance:**
```bash
aws rds describe-db-instances \
  --db-instance-identifier <id> \
  --region <region>
```
→ Check `EngineVersion` field

**Lambda Function:**
```bash
aws lambda get-function \
  --function-name <name> \
  --region <region>
```
→ Check `Runtime` field

**For other services (EKS, ECS, MSK, ElastiCache, OpenSearch, EC2, ELB):**
Read references/VERIFICATION.md Table of Contents for service-specific APIs.

---

### Step 6: Compare & Report

**Verification logic:**

```python
if current_version in eol_versions:
    conclusion = "❌ Not resolved"
    confidence = 100
elif resource_not_found:
    conclusion = "🔵 Cannot verify (deleted/replaced?)"
    confidence = 70
else:
    conclusion = "✅ Resolved (upgraded)"
    confidence = 95
```

**Always provide evidence:** Cite specific field values from API responses.

**For report format:** Read references/OUTPUT-FORMATS.md

## Mandatory Verification Policy

**DO NOT SKIP ANY STEP**

For EVERY PLANNED_LIFECYCLE_EVENT:

1. ✅ Get event details
2. ✅ Parse EOL versions (eventMetadata or latestDescription)
3. ✅ Get affected resources (ALL pages)
4. ✅ Query EVERY resource's current state
5. ✅ Compare current vs EOL version
6. ✅ Output clear conclusion with confidence score

**No exceptions for:**
- Expired events (verify MORE, not less - users may have forgotten)
- Old events (provide current actual state)
- "Probably resolved" guesses (query actual state)
- Partial verification (all resources, or explain why)

**Only mark "Cannot Verify" (🔵) when:**
- No Business/Enterprise Support (Health API unavailable)
- Service not supported (see VERIFICATION.md Table of Contents)
- Permission denied (AccessDenied error)
- Resource not found (mark as 🔵, confidence 70%)
- Configuration change event (not a resource EOL)

**Verification Completeness Checklist:**

Before outputting report, confirm:
- [ ] All EOL events fetched event details
- [ ] All EOL events fetched affected resource lists (all pages)
- [ ] All affected resources queried
- [ ] All results have ✅/❌/🔵 status
- [ ] All ❌ have specific remediation steps
- [ ] All 🔵 explain why verification failed

## When to Read References

**Always read references/VERIFICATION.md when:**
- Starting verification (load workflow and tool call templates)
- Verifying unfamiliar service (load service-specific section)
- Handling pagination or errors

**Always read references/OUTPUT-FORMATS.md when:**
- Generating final report
- Unsure about table format or evidence presentation

**Tip:** VERIFICATION.md has Table of Contents - only load relevant service sections.

## Common Pitfalls

❌ Listing events without verification
Good: "5 events found. Verified all: luchen ✅ upgraded. All resolved."
Bad: "You have 5 events. You should upgrade."

❌ "Suggest checking" instead of actually checking
Good: "Verified: 1 instance upgraded. No action needed."
Bad: "Event expired. Suggest checking if instances still running EOL."

❌ Missing EOL version info
Good: "EOL: v1,v2. Current: v3. ✅ Resolved."
Bad: "Version is v3. Status unknown."

❌ No evidence
Good: "Evidence: PlatformIdentifier=v3, LastModifiedTime=2026-03-09"
Bad: "Resource appears upgraded."

❌ Skipping expired events
Good: "Expired 9 months ago. Verified: ✅ Upgraded."
Bad: "Expired, skipping."

❌ Partial verification
Good: "Checked all 5 events affecting 1 instance. All resolved."
Bad: "Checked 2 of 5 events."

## Tool Usage

Use call_aws tool for all AWS API operations.

Basic pattern:

    call_aws(
        cli_command="aws <service> <operation> <parameters> --region <region>",
        role_arn="<from config.yaml>"
    )

All tool call details in references/VERIFICATION.md.

## Prerequisites

Requires Business or Enterprise Support to use Health API.

Without support: Suggest EventBridge rules for PHD monitoring.

## Important Notes

- PHD events persist even after issues resolved
- Goal: Verify if underlying issue fixed, not just list events
- Always get full API responses (no --query filtering)
- Provide specific evidence from API fields
- Report confidence scores for all conclusions
