let currentTaskId = null;
let pollInterval = null;

function setGoal(goalText) {
    document.getElementById("goal-input").value = goalText;
    showToast(`Loaded scenario: ${goalText}`);
}

async function startTask() {
    const goalInput = document.getElementById("goal-input").value.trim();
    if (!goalInput) {
        showToast("Please enter a goal first", "error");
        return;
    }

    const startBtn = document.getElementById("btn-start-task");
    startBtn.disabled = true;
    startBtn.textContent = "Agent Executing...";

    updateAgentStatusBadge("running");
    hideApprovalCard();

    try {
        const response = await fetch("/api/tasks", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ goal: goalInput })
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Task execution failed");
        }

        const data = await response.json();
        currentTaskId = data.taskId;
        document.getElementById("current-task-id").textContent = currentTaskId;

        renderTaskState(data.state);
        showToast(`Task ${currentTaskId} initiated`);

    } catch (err) {
        showToast(err.message, "error");
        updateAgentStatusBadge("failed");
    } finally {
        startBtn.disabled = false;
        startBtn.innerHTML = `
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
            Dispatch Autonomous Agent
        `;
    }
}

function renderTaskState(state) {
    // 1. Status Badges
    updateAgentStatusBadge(state.final_status);
    document.getElementById("retry-counter").textContent = `${state.retry_count || 0} / ${state.max_retries || 1}`;

    // 2. Verification Badge
    const verifBadge = document.getElementById("verification-status-badge");
    const isVerified = state.verification && state.verification.verified;
    if (isVerified) {
        verifBadge.textContent = "VERIFIED (LEDGER + TICKET)";
        verifBadge.className = "agent-badge verified";
    } else if (state.final_status === "failed_verification") {
        verifBadge.textContent = "VERIFICATION FAILED";
        verifBadge.className = "agent-badge failed";
    } else {
        verifBadge.textContent = "UNVERIFIED";
        verifBadge.className = "agent-badge unverified";
    }

    // 3. Human Approval Gate
    if (state.final_status === "paused_for_approval" && state.approval_required) {
        showApprovalCard(state);
    } else {
        hideApprovalCard();
    }

    // 4. Render Dynamic Plan
    renderPlan(state.plan, state.current_step, state.final_status);

    // 5. Render Trace
    renderTrace(state.trace);

    // 6. Render Evidence & Summary
    document.getElementById("executive-summary-text").textContent = state.summary || "Agent task currently executing...";
    document.getElementById("evidence-json-viewer").textContent = JSON.stringify(state.evidence || {}, null, 2);
    document.getElementById("evidence-status-pill").textContent = state.final_status.toUpperCase();
}

function renderPlan(plan, currentStep, finalStatus) {
    const container = document.getElementById("plan-container");
    if (!plan || plan.length === 0) {
        container.innerHTML = '<div class="empty-state">No plan available.</div>';
        return;
    }

    container.innerHTML = "";
    plan.forEach((item, index) => {
        const div = document.createElement("div");
        const isCompleted = finalStatus === "completed";
        div.className = `plan-item ${isCompleted ? "completed" : ""}`;

        div.innerHTML = `
            <div class="plan-item-num">${item.id || index + 1}</div>
            <div class="plan-item-content">
                <div class="plan-item-title">${item.description}</div>
                <div class="plan-item-desc">Action: <strong>${item.action}</strong></div>
                <span class="plan-tool-tag">${item.tool || "system_reasoning"}</span>
            </div>
        `;
        container.appendChild(div);
    });
}

function renderTrace(trace) {
    const container = document.getElementById("trace-container");
    document.getElementById("trace-step-count").textContent = `${trace.length} Steps`;

    if (!trace || trace.length === 0) {
        container.innerHTML = '<div class="empty-state">No trace steps yet.</div>';
        return;
    }

    container.innerHTML = "";
    trace.forEach(step => {
        const div = document.createElement("div");
        div.className = `trace-item phase-${step.phase}`;

        const statusClass = step.status.toLowerCase();
        const source = step.decision_source || "deterministic safety rule";
        const sourceSlug = source.toLowerCase().replace(/[^a-z0-9]/g, "-");

        let reasoningHtml = "";
        if (step.reasoning) {
            reasoningHtml = `<div class="trace-reasoning"><strong>Reasoning:</strong> ${escapeHtml(step.reasoning)}</div>`;
        }

        div.innerHTML = `
            <div class="trace-header">
                <span class="trace-action">${step.phase.toUpperCase()} &bull; ${step.action}</span>
                <div class="trace-meta-tags">
                    <span class="trace-source-pill source-${sourceSlug}">${source}</span>
                    <span class="trace-status-pill ${statusClass}">${step.status}</span>
                </div>
            </div>
            ${reasoningHtml}
            <div class="trace-details">${escapeHtml(step.details)}</div>
        `;
        container.appendChild(div);
    });

    container.scrollTop = container.scrollHeight;
}

function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function showApprovalCard(state) {
    const banner = document.getElementById("approval-gate-banner");
    const metaBox = document.getElementById("approval-meta-box");
    const desc = document.getElementById("approval-description");

    const amount = state.payment ? state.payment.amount : "N/A";
    const custName = state.customer ? state.customer.name : "N/A";
    const ticketId = state.ticket ? state.ticket.id : "N/A";
    const paymentId = state.payment ? state.payment.id : "N/A";

    desc.textContent = `A refund of ₹${amount} exceeds the automatic approval threshold of ₹5,000. Managerial approval is required.`;

    metaBox.innerHTML = `
        <div>
            <span class="meta-field-label">Customer</span>
            <span class="meta-field-val">${custName}</span>
        </div>
        <div>
            <span class="meta-field-label">Ticket ID</span>
            <span class="meta-field-val">${ticketId}</span>
        </div>
        <div>
            <span class="meta-field-label">Payment ID</span>
            <span class="meta-field-val">${paymentId}</span>
        </div>
        <div>
            <span class="meta-field-label">Requested Refund</span>
            <span class="meta-field-val" style="color: #c084fc;">₹${amount}</span>
        </div>
    `;

    banner.classList.remove("hidden");
}

function hideApprovalCard() {
    document.getElementById("approval-gate-banner").classList.add("hidden");
}

async function submitApprovalDecision(approved) {
    if (!currentTaskId) return;

    const endpoint = approved ? `/api/tasks/${currentTaskId}/approve` : `/api/tasks/${currentTaskId}/reject`;
    const notes = approved ? "Approved by operations manager via dashboard." : "Rejected: Refund exceeds budget limit.";

    try {
        const response = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ decision_notes: notes })
        });

        if (!response.ok) throw new Error("Failed to process approval decision");
        const data = await response.json();
        renderTaskState(data.state);
        showToast(approved ? "Refund approved! Resumed execution." : "Refund rejected! Ticket closed safely.");
    } catch (err) {
        showToast(err.message, "error");
    }
}

function updateAgentStatusBadge(status) {
    const badge = document.getElementById("agent-status-badge");
    badge.textContent = (status || "idle").toUpperCase();
    badge.className = `agent-badge ${status || "idle"}`;
}

async function resetDatabase() {
    if (!confirm("Are you sure you want to reset all mock databases, tickets, and payments?")) return;
    try {
        const res = await fetch("/api/db/reset", { method: "POST" });
        if (res.ok) {
            showToast("Mock database reset to initial seed state!");
            document.getElementById("plan-container").innerHTML = '<div class="empty-state">Database reset. Ready for new task.</div>';
            document.getElementById("trace-container").innerHTML = '<div class="empty-state">Ready.</div>';
            document.getElementById("evidence-json-viewer").textContent = "{}";
            document.getElementById("executive-summary-text").textContent = "Database reset. Ready for new task.";
            updateAgentStatusBadge("idle");
            hideApprovalCard();
        }
    } catch (err) {
        showToast("Failed to reset database", "error");
    }
}

async function runPlaywrightInspect() {
    const ticketId = document.getElementById("pw-ticket-id").value.trim() || "TICKET1024";
    const resultBox = document.getElementById("pw-result");
    resultBox.classList.remove("hidden");
    resultBox.textContent = `Launching Chromium to inspect ${ticketId} in Mock Portal...`;

    try {
        const res = await fetch("/api/browser/inspect", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticket_id: ticketId })
        });
        const data = await res.json();
        resultBox.textContent = JSON.stringify(data, null, 2);
        showToast("Playwright Chromium inspection completed!");
    } catch (err) {
        resultBox.textContent = `Browser error: ${err.message}`;
    }
}

function showToast(message, type = "info") {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.style.borderColor = type === "error" ? "var(--danger)" : "var(--border-accent)";
    toast.classList.remove("hidden");
    setTimeout(() => {
        toast.classList.add("hidden");
    }, 3500);
}

async function checkSystemStatus() {
    try {
        const res = await fetch("/api/system/status");
        if (res.ok) {
            const data = await res.json();
            const badge = document.getElementById("ai-engine-badge");
            if (badge) {
                if (data.hasKey) {
                    badge.className = "agent-badge live-gemini";
                    badge.textContent = `Gemini (${data.model} | Live)`;
                } else {
                    badge.className = "agent-badge fallback-engine";
                    badge.textContent = "Deterministic Fallback (Offline)";
                }
            }
        }
    } catch (e) {
        console.warn("Status check error:", e);
    }
}

window.addEventListener("DOMContentLoaded", () => {
    checkSystemStatus();
});
