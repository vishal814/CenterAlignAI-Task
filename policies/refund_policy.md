# Enterprise Refund Policy & Standard Operating Procedure (SOP)

## 1. Scope & Objective
This Standard Operating Procedure (SOP) defines the protocol for resolving customer payment disputes, unfulfilled subscriptions, and billing grievances across CentrAlign AI enterprise platforms.

## 2. Refund Eligibility & Approval Thresholds
- **Tier 1 (Automatic Autonomous Approval)**:
  - Refunds with amounts less than or equal to ₹5,000 (INR 5,000) may be processed automatically by the AI Operator without manual human intervention.
  - Prerequisites: Valid payment record confirmed as `charged`, customer identity matched, and no prior completed refund on record for this transaction.
- **Tier 2 (Mandatory Human Approval Gate)**:
  - Any refund with an amount strictly greater than ₹5,000 (INR 5,000) REQUIRES explicit human managerial approval.
  - The AI Operator MUST pause task execution, notify the operations manager with full contextual metadata, and await approval before triggering the payment gateway.
  - If rejected by the human manager, the refund must not be executed and the ticket must be annotated with the rejection reason.

## 3. Duplicate Prevention & Fraud Safeguards
- Under NO circumstance may a duplicate refund be issued for a payment that already has a completed or processed refund (`refund_status == 'completed'`).
- If an existing refund is discovered, the AI Operator must halt further disbursement, update the associated support ticket to reference the existing refund ID, and independently verify the record.

## 4. Verification & Audit Trail Mandate
- Every action must be verified independently. Action success (e.g., API returning HTTP 200) is NOT considered proof of task completion.
- The AI Operator must independently query the payment ledger to confirm the refund transaction was persisted.
- The AI Operator must independently query the ticketing system to confirm the ticket status has transitioned to `resolved` with resolution notes attached.
- A structured evidence payload must be generated upon verification.

## 5. Failure Handling & Recovery
- Transient gateway errors (`temporary_payment_service_error`) may be retried up to 1 time.
- Permanent errors (e.g., customer not found, invalid ticket, missing payment record) must not be retried and must fail safely with full error context.
