# Output Formats

Report templates for PHD verification results.

## Standard Report Structure

    ## PHD Verification Report - Account {account_id}
    
    **Generated:** {timestamp}
    **Total EOL Events:** X
    **Resolved:** Y ✅
    **Not Resolved:** Z ❌
    **Cannot Verify:** W 🔵
    
    ---
    
    [Individual event sections - see templates below]
    
    ---
    
    ## Summary
    
    [Priority-sorted action items]

---

## Event Templates

### ✅ Resolved Event

    ### ✅ Resolved: [Service] [Event Type]
    
    **Event ARN:** [arn]
    **EOL Date:** [date]
    **EOL Versions:** [v1, v2]
    **Affected Resources:** X resources
    
    **Verification (ALL resources checked):**
    
    | Resource | Current Version | Status | Confidence | Last Modified |
    |----------|----------------|--------|------------|---------------|
    | name1    | v3             | ✅ Resolved | 100% | 2026-03-09 |
    
    **Evidence:**
    PlatformIdentifier: notebook-al2-v3
    NotebookInstanceStatus: InService
    LastModifiedTime: 2026-03-09T20:44:56Z
    
    **Conclusion:** ✅ All resources resolved (Confidence: 100%)

### ❌ Not Resolved Event

    ### ❌ Not Resolved: [Service] [Event Type]
    
    **Event ARN:** [arn]
    **EOL Date:** [date]
    **EOL Versions:** [v1, v2]
    **Affected Resources:** X resources
    
    **Verification (ALL resources checked):**
    
    | Resource | Current Version | Status | Confidence | Issue |
    |----------|----------------|--------|------------|-------|
    | name1    | v1 (EOL)       | ❌ Not Resolved | 100% | Still running EOL version |
    
    **Evidence:**
    EngineVersion: 5.7.44
    DBInstanceStatus: available
    LastModifiedTime: 2024-01-15T10:30:00Z
    
    **Action Required:**
    1. [Specific remediation step]
    2. [Specific remediation step]
    
    **Conclusion:** ❌ Not resolved (Confidence: 100%)

### 🔵 Cannot Verify Event

    ### 🔵 Cannot Verify: [Service] [Event Type]
    
    **Event ARN:** [arn]
    **EOL Date:** [date]
    **Affected Resources:** X resources
    
    **Verification (attempted):**
    
    | Resource | Status | Reason |
    |----------|--------|--------|
    | name1    | 🔵 Cannot Verify | ResourceNotFoundException |
    
    **Analysis:**
    [Why verification failed - permissions, deleted resources, etc.]
    
    **Suggestion:**
    [How to manually verify or resolve]
    
    **Conclusion:** 🔵 Cannot verify (Confidence: 70%)

### 📋 Configuration Change Event

For non-resource EOL events (EventBridge behavior changes, service updates):

    ### 📋 Configuration Change: [Event Type]
    
    **Event ARN:** [arn]
    **Effective Date:** [date]
    
    **Change Summary:**
    [What's changing]
    
    **Impact:**
    [How it affects the account]
    
    **Action Required:**
    1. [Specific configuration steps]
    
    **Conclusion:** 📋 Configuration action required before [date]

---

## Summary Section

Always include at end of report:

    ## Summary
    
    ### By Priority
    
    🔴 **High Priority (< 3 months):**
    - ❌ [Service] [Event] ([date]): [status]
    
    ⚠️ **Medium Priority (3-6 months):**
    - [Event] ([date]): [status]
    
    📋 **Low Priority (> 6 months):**
    - [Event] ([date]): [status]
    
    ✅ **Resolved:**
    - ✅ [Service] [Event]: [brief summary]
    
    ### Next Steps
    
    #### Immediate (this week)
    - [ ] [Action item]
    
    #### Short-term (this month)
    - [ ] [Action item]

---

## Confidence Scores

**100%:** Definitive API evidence (version field matches/differs from EOL)

**90-95%:** Resource deleted (ResourceNotFoundException), likely resolved but not certain

**70-90%:** Mixed signals, partial information, indirect evidence

**50-70%:** Ambiguous state, requires human review

**< 50%:** Cannot determine - mark as 🔵 Cannot Verify instead

---

## Evidence Formatting

Format as key-value pairs (not full JSON). Include only relevant fields.

Good:

    Evidence:
    EngineVersion: 5.7.44
    DBInstanceStatus: available
    LastModifiedTime: 2024-01-15T10:30:00Z

Bad:

    Evidence: See API response (too vague)
    Evidence: { "DBInstanceIdentifier": "prod-db-1", ... } (full JSON)

---

## Table Formatting

For resolved events:

    | Resource | Current Version | Status | Confidence | Last Modified |

For not resolved events:

    | Resource | Current Version | Status | Confidence | Issue |

For cannot verify events:

    | Resource | Status | Reason |
