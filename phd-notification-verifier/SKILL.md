---
name: phd-verifier
description: Verify AWS Personal Health Dashboard events and check if reported issues have been resolved. Use when: (1) Customer asks to check PHD notifications, (2) Need to verify if EOL/deprecation events are resolved (RDS version, SageMaker platform, Lambda runtime, etc.), (3) Validate maintenance windows completed, (4) Check if retirement/certificate expiry issues addressed. Specializes in EOL event verification by comparing current resource versions with deprecated versions.
---

# PHD Notification Verifier

Verify AWS Personal Health Dashboard events by checking if underlying issues are resolved.

## Core Value: EOL Event Verification

**Primary use case:** Verify End-of-Life (EOL) and deprecation events across all AWS services.

**How it works:**
1. Get PHD events via `call_aws` tool (Health API)
2. Extract affected resources from event
3. Query current resource state (version/platform/runtime)
4. Compare with EOL versions from event description
5. Provide confidence score + evidence

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

### Step 1: Get PHD Events

```
call_aws(
  cli_command: "aws health describe-events --filter eventStatusCodes=open,upcoming --max-results 100 --region cn-northwest-1",
  role_arn: "arn:aws-cn:iam::123456789012:role/RoleName"
)
```

**Pagination Handling:**

Health API returns max 100 events per call. If response contains `nextToken`, continue fetching:

```
# First call
response1 = call_aws("aws health describe-events --filter eventStatusCodes=open --max-results 100 --region cn-northwest-1")

# If nextToken exists, continue
if response1.nextToken:
    response2 = call_aws(f"aws health describe-events --filter eventStatusCodes=open --max-results 100 --next-token {response1.nextToken} --region cn-northwest-1")

# Repeat until nextToken is null
```

**Important:**
- Always check for `nextToken` in response
- Don't assume all events are returned in one call
- For customers with many events (>100), pagination is critical
- Aggregate all pages before processing

**Note:** Health API is global, but region must be specified:
- China: `cn-northwest-1` or `cn-north-1`
- Global: `us-east-1`

### Step 2: Get Affected Resources

```
call_aws(
  cli_command: "aws health describe-affected-entities --filter eventArns=<arn> --max-results 100 --region cn-northwest-1",
  role_arn: "arn:aws-cn:iam::123456789012:role/RoleName"
)
```

**Pagination Handling:**

Similar to describe-events, affected-entities also supports pagination:

```
# First call
entities1 = call_aws("aws health describe-affected-entities --filter eventArns=<arn> --max-results 100 --region cn-northwest-1")

# If nextToken exists, continue
if entities1.nextToken:
    entities2 = call_aws(f"aws health describe-affected-entities --filter eventArns=<arn> --max-results 100 --next-token {entities1.nextToken} --region cn-northwest-1")

# Repeat until nextToken is null
```

**Important:**
- A single PHD event may affect hundreds of resources
- Always paginate to get complete list
- Example: RDS version EOL might affect 200+ instances

### Step 3: Verify Resource State

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
