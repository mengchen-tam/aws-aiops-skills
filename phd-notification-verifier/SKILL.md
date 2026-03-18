---
name: phd-verifier
description: Verify AWS Personal Health Dashboard events and check if reported issues have been resolved. Use when: (1) Customer asks to check PHD notifications, (2) Need to verify if EOL/deprecation events are resolved (RDS version, SageMaker platform, Lambda runtime, etc.), (3) Validate maintenance windows completed, (4) Check if retirement/certificate expiry issues addressed. Specializes in EOL event verification by comparing current resource versions with deprecated versions.
---

# PHD Notification Verifier

Verify AWS Personal Health Dashboard events by checking if underlying issues are resolved.

## Core Value: EOL Event Verification

**Primary use case:** Verify End-of-Life (EOL) and deprecation events across all AWS services.

**How it works:**
1. Get PHD events via `describe-events`
2. Get detailed event info via `describe-event-details` (EOL versions, dates)
3. Extract affected resources via `describe-affected-entities`
4. Query current resource state (version/platform/runtime)
5. Compare current state with EOL info from event details
6. Provide confidence score + evidence

**Why this matters:** PHD events persist even after issues are resolved. Manual verification is time-consuming (15-20 min per event). This skill automates the verification, saving 85% of time.

## Prerequisites

### Tools Required

**Primary: `call_aws` tool (MCP Hub)**
```
call_aws(
  cli_command: "aws <service> <operation> ...",
  role_arn: "arn:aws-cn:iam::123456789012:role/RoleName"
)
```

**Fallback: AWS CLI**
```bash
aws <service> <operation> --profile <profile>
```

### AWS Health API Requirements

**⚠️ Requires Business or Enterprise Support**

Without support plan:
- API returns `SubscriptionRequiredException`
- Suggest: Set up EventBridge rules for future notifications
- Cannot proceed with verification

## Tool Usage

### Step 1: Get Scheduled Change Events

```
call_aws(
  cli_command: "aws health describe-events --filter eventTypeCategories=scheduledChange eventStatusCodes=open,upcoming --max-results 100 --region cn-northwest-1",
  role_arn: "arn:aws-cn:iam::123456789012:role/RoleName"
)
```

**Pagination:**
- Health API returns max 100 events per call
- Check `nextToken` in response
- Continue with `--next-token <token>` until no more pages

**Region:**
- China: `cn-northwest-1` or `cn-north-1`
- Global: `us-east-1`

### Step 1.5: Filter EOL Events

From describe-events results, keep only EOL events:
```
eol_events = [e for e in events if "PLANNED_LIFECYCLE_EVENT" in e["eventTypeCode"]]
```

**Rationale:**
- `scheduledChange` includes both EOL and non-EOL events
- EOL events: `AWS_{SERVICE}_PLANNED_LIFECYCLE_EVENT`
- Non-EOL: maintenance (`AWS_*_SCHEDULED_MAINTENANCE`), retirement (`AWS_EC2_INSTANCE_RETIREMENT_SCHEDULED`)
- Client-side filtering reduces token cost (~45% savings)

### Step 2: Get Event Details (EOL Info)

**Only for filtered EOL events from Step 1.5:**

```
call_aws(
  cli_command: "aws health describe-event-details --event-arns <arn1> <arn2> --region cn-northwest-1",
  role_arn: "arn:aws-cn:iam::123456789012:role/RoleName"
)
```

**Batch processing:**
- API supports up to 10 event ARNs per call
- Batch EOL events into groups of 10

**Returns:**
- `eventDescription.latestDescription` - Detailed text with EOL version/date
- `eventMetadata` - Structured fields (EOL_DATE, EOL_VERSION, SUPPORTED_VERSION)
- `event.startTime`, `event.endTime` - Event timeline

**Example metadata:**
```json
{
  "eventMetadata": {
    "EOL_DATE": "2024-06-30",
    "EOL_VERSION": "notebook-al2-v1",
    "SUPPORTED_VERSION": "notebook-al2-v3"
  }
}
```

### Step 3: Get Affected Resources

```
call_aws(
  cli_command: "aws health describe-affected-entities --filter eventArns=<arn> --max-results 100 --region cn-northwest-1",
  role_arn: "arn:aws-cn:iam::123456789012:role/RoleName"
)
```

**Pagination:**
- A single event may affect hundreds of resources
- Check `nextToken` and continue with `--next-token <token>`
- Aggregate all pages before processing

### Step 4: Verify Resource State

**Service-specific queries** - See [VERIFICATION.md](references/VERIFICATION.md) for complete list.

**Key principle:** Get FULL resource details (don't filter fields with --query)

Example for SageMaker:
```
call_aws(
  cli_command: "aws sagemaker describe-notebook-instance --notebook-instance-name <name> --region cn-north-1",
  role_arn: "arn:aws-cn:iam::123456789012:role/RoleName"
)
```

Check `PlatformIdentifier` field in response.

## Verification Logic

### Generic EOL Pattern (All Services)

```
IF current_version IN eol_versions:
    ❌ Not resolved
ELIF current_version NOT IN eol_versions:
    ✅ Resolved (95% confidence)
ELIF resource_not_found:
    ✅ Deleted/replaced (90% confidence)
ELSE:
    ⚠️ Uncertain (60% confidence)
```

### Service-Specific Details

See [VERIFICATION.md](references/VERIFICATION.md) for:
- Service-by-service verification commands
- Field names to check
- EOL version lists
- Common patterns

## Confidence Scoring

- **95-100%**: Definitive evidence (version changed, resource deleted)
- **70-95%**: Strong indicators (modification after EOL date)
- **50-70%**: Mixed signals (need human review)
- **<50%**: Not resolved or cannot determine

**Provide evidence:** Always cite specific field values from API responses.

## Output Format

```markdown
## Event: [Service] [Type]

**Affected Resource:** [ARN or name]
**EOL Date:** [Date]
**Current State:**
- [Key field]: [Value] [✅/❌]
- [Key field]: [Value] [✅/❌]

**Evidence:**
[Specific API response fields]

**Confidence:** [Score]%
**Conclusion:** [Resolved/Not resolved/Uncertain]
```

## Common Errors

### SubscriptionRequiredException
```
Error: AWS Health API requires Business or Enterprise Support
```
**Response:** Account lacks support plan. Suggest EventBridge rules.

### InvalidParameterValueException
**Cause:** Wrong region
**Fix:** Use cn-northwest-1 (China) or us-east-1 (Global)

### AccessDeniedException
**Cause:** Missing IAM permissions
**Fix:** Verify role has `health:*` permissions

## Cross-Account Configuration

**MCP Hub:**
```
role_arn: "arn:aws-cn:iam::123456789012:role/RoleName"
external_id: "optional-external-id"
```

**AWS CLI:**
```ini
[profile account-a]
role_arn = arn:aws-cn:iam::123456789012:role/RoleName
source_profile = default
```

## Important Notes

- PHD events cannot be closed via API
- Goal: Verify if underlying issue is resolved
- Focus on EOL events for highest value
- Always get full API responses (no --query filtering)
- Provide specific evidence from API fields
