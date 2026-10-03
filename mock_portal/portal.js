let currentTicketId = null;

async function searchTicket() {
    const input = document.getElementById("ticket-search-input").value.trim();
    if (!input) return;

    showLoading(true);
    clearResultMsg();

    try {
        let ticket = null;
        let customer = null;

        // Try direct ticket ID lookup first
        if (input.toUpperCase().startsWith("TICKET")) {
            const res = await fetch(`/api/tickets/${encodeURIComponent(input.toUpperCase())}`);
            if (res.ok) {
                ticket = await res.json();
            }
        }

        // If not found, try searching by customer or issue query
        if (!ticket) {
            const searchRes = await fetch(`/api/tickets/search?query=${encodeURIComponent(input)}`);
            if (searchRes.ok) {
                const list = await searchRes.json();
                if (list.length > 0) ticket = list[0];
            }
        }

        if (ticket) {
            currentTicketId = ticket.id;
            // Fetch customer info
            const custRes = await fetch(`/api/customers/${ticket.customer_id}`);
            if (custRes.ok) customer = await custRes.json();

            // Fetch payment info if available
            let paymentAmount = "N/A";
            if (ticket.payment_id) {
                const payRes = await fetch(`/api/payments/${ticket.payment_id}`);
                if (payRes.ok) {
                    const pay = await payRes.json();
                    paymentAmount = `₹${pay.amount.toFixed(2)}`;
                }
            }

            renderTicket(ticket, customer, paymentAmount);
        } else {
            alert(`No tickets found matching '${input}'`);
        }
    } catch (err) {
        console.error("Portal error:", err);
        alert("Failed to communicate with enterprise backend.");
    } finally {
        showLoading(false);
    }
}

function renderTicket(ticket, customer, paymentAmount) {
    document.getElementById("card-ticket-id").textContent = ticket.id;
    document.getElementById("card-ticket-issue").textContent = ticket.issue;
    
    const badge = document.getElementById("ticket-status-badge");
    badge.textContent = ticket.status.toUpperCase();
    badge.className = `badge badge-${ticket.status.toLowerCase()}`;

    document.getElementById("detail-customer-id").textContent = ticket.customer_id;
    document.getElementById("detail-customer-name").textContent = customer ? customer.name : "Unknown";
    document.getElementById("detail-payment-id").textContent = ticket.payment_id || "None";
    document.getElementById("detail-amount").textContent = paymentAmount;

    document.getElementById("ticket-notes-textarea").value = ticket.notes || "";

    document.getElementById("ticket-details-card").classList.remove("hidden");
}

async function markResolved() {
    if (!currentTicketId) return;

    const notes = document.getElementById("ticket-notes-textarea").value.trim();
    const resultMsg = document.getElementById("ticket-result-message");

    try {
        const res = await fetch(`/api/tickets/${currentTicketId}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                status: "resolved",
                notes: notes ? `[Manual Portal Resolution]: ${notes}` : "[Manual Portal Resolution]: Marked resolved via portal UI."
            })
        });

        if (res.ok) {
            const updated = await res.json();
            const badge = document.getElementById("ticket-status-badge");
            badge.textContent = "RESOLVED";
            badge.className = "badge badge-resolved";
            resultMsg.textContent = "✓ Ticket successfully marked as RESOLVED";
            resultMsg.style.color = "#10b981";
            loadAllTickets();
        } else {
            resultMsg.textContent = "✗ Failed to update ticket status";
            resultMsg.style.color = "#ef4444";
        }
    } catch (err) {
        resultMsg.textContent = `✗ Error: ${err.message}`;
        resultMsg.style.color = "#ef4444";
    }
}

async function loadAllTickets() {
    try {
        const res = await fetch("/api/tickets");
        if (!res.ok) return;
        const tickets = await res.json();
        const tbody = document.getElementById("tickets-table-body");
        tbody.innerHTML = "";

        for (const t of tickets) {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><code>${t.id}</code></td>
                <td>${t.customer_id}</td>
                <td>${t.issue}</td>
                <td><code>${t.payment_id || "-"}</code></td>
                <td><span class="badge badge-${t.status.toLowerCase()}">${t.status.toUpperCase()}</span></td>
                <td><button class="btn-secondary" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;" onclick="inspectTicket('${t.id}')">Inspect</button></td>
            `;
            tbody.appendChild(tr);
        }
    } catch (err) {
        console.error("Failed to load tickets:", err);
    }
}

function inspectTicket(ticketId) {
    document.getElementById("ticket-search-input").value = ticketId;
    searchTicket();
}

function showLoading(show) {
    const spinner = document.getElementById("loading-spinner");
    if (show) spinner.classList.remove("hidden");
    else spinner.classList.add("hidden");
}

function clearResultMsg() {
    document.getElementById("ticket-result-message").textContent = "";
}

// Initial load
window.addEventListener("DOMContentLoaded", () => {
    loadAllTickets();
    searchTicket();
});
