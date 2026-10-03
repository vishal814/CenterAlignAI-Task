import os
from pathlib import Path
from typing import Dict, Any, Optional
from playwright.sync_api import sync_playwright
from app.config import settings

def inspect_ticket_in_browser(ticket_id: str, portal_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Genuine browser automation using Playwright.
    Launches Chromium, navigates to the enterprise support portal, searches for the ticket,
    inspects the live DOM, captures a screenshot, and extracts visible customer and ticket state.
    """
    url = portal_url or f"http://{settings.HOST}:{settings.PORT}/portal"
    screenshot_dir = Path(settings.DATABASE_PATH).parent / "mock_portal" / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    screenshot_file = screenshot_dir / f"ticket_{ticket_id}.png"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=settings.PLAYWRIGHT_HEADLESS)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            
            # 1. Navigate to support portal
            page.goto(url, wait_until="networkidle", timeout=15000)

            # 2. Fill search box and submit
            page.fill("#ticket-search-input", ticket_id)
            page.click("#ticket-search-btn")

            # 3. Wait for ticket details card to appear
            page.wait_for_selector("#ticket-details-card:not(.hidden)", timeout=10000)

            # 4. Extract visible state from the DOM
            extracted_ticket_id = page.inner_text("#card-ticket-id").strip()
            issue = page.inner_text("#card-ticket-issue").strip()
            status = page.inner_text("#ticket-status-badge").strip()
            customer_id = page.inner_text("#detail-customer-id").strip()
            customer_name = page.inner_text("#detail-customer-name").strip()
            payment_id = page.inner_text("#detail-payment-id").strip()
            amount = page.inner_text("#detail-amount").strip()

            # 5. Capture actual screenshot
            page.screenshot(path=str(screenshot_file))
            browser.close()

            return {
                "success": True,
                "browser": "chromium",
                "portalUrl": url,
                "ticketId": ticket_id,
                "domExtracted": {
                    "ticketId": extracted_ticket_id,
                    "issue": issue,
                    "status": status,
                    "customerId": customer_id,
                    "customerName": customer_name,
                    "paymentId": payment_id,
                    "amount": amount
                },
                "screenshotSaved": True,
                "screenshotPath": str(screenshot_file),
                "message": f"Successfully inspected ticket {ticket_id} via Playwright browser automation."
            }
    except Exception as e:
        return {
            "success": False,
            "browser": "chromium",
            "portalUrl": url,
            "ticketId": ticket_id,
            "error": f"Browser automation error: {str(e)}"
        }

def resolve_ticket_in_browser(ticket_id: str, notes: str, portal_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Genuine browser automation updating a ticket via the web portal UI using Playwright.
    """
    url = portal_url or f"http://{settings.HOST}:{settings.PORT}/portal"
    screenshot_dir = Path(settings.DATABASE_PATH).parent / "mock_portal" / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    screenshot_file = screenshot_dir / f"resolved_{ticket_id}.png"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=settings.PLAYWRIGHT_HEADLESS)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(url, wait_until="networkidle", timeout=15000)

            page.fill("#ticket-search-input", ticket_id)
            page.click("#ticket-search-btn")
            page.wait_for_selector("#ticket-details-card:not(.hidden)", timeout=10000)

            # Enter notes into textarea
            page.fill("#ticket-notes-textarea", notes)

            # Click mark as resolved
            page.click("#ticket-resolve-btn")

            # Wait for status badge to reflect RESOLVED
            page.wait_for_selector("#ticket-status-badge.badge-resolved", timeout=10000)
            page.wait_for_selector("#ticket-result-message", timeout=5000)

            final_status = page.inner_text("#ticket-status-badge").strip()
            result_msg = page.inner_text("#ticket-result-message").strip()

            page.screenshot(path=str(screenshot_file))
            browser.close()

            return {
                "success": True,
                "ticketId": ticket_id,
                "portalUrl": url,
                "finalStatus": final_status,
                "resultMessage": result_msg,
                "screenshotSaved": True,
                "screenshotPath": str(screenshot_file),
                "message": f"Successfully updated ticket {ticket_id} to {final_status} via Playwright."
            }
    except Exception as e:
        return {
            "success": False,
            "ticketId": ticket_id,
            "error": f"Browser update error: {str(e)}"
        }
