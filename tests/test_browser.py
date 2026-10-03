import pytest
import time
import threading
import uvicorn
from app.main import app
from app.tools.browser_tools import inspect_ticket_in_browser, resolve_ticket_in_browser

@pytest.fixture(scope="module")
def live_server():
    """Start uvicorn server in a background thread for browser automation testing."""
    port = 8899
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config=config)
    
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    time.sleep(1.5)  # Wait for server to bind and start listening
    
    portal_url = f"http://127.0.0.1:{port}/portal"
    yield portal_url
    
    server.should_exit = True

def test_playwright_browser_inspection(live_server):
    """
    Genuine browser automation test using Playwright.
    Launches Chromium, navigates to the mock support portal, searches TICKET1024,
    extracts visible DOM elements, and verifies screenshot creation.
    """
    res = inspect_ticket_in_browser("TICKET1024", portal_url=live_server)
    assert res["success"] is True
    assert res["browser"] == "chromium"
    assert res["screenshotSaved"] is True
    
    dom = res["domExtracted"]
    assert dom["ticketId"] == "TICKET1024"
    assert dom["customerName"] == "Rahul Sharma"
    assert "2499" in dom["amount"]
    assert dom["status"] == "OPEN"

def test_playwright_browser_resolution(live_server):
    """
    Genuine browser automation test resolving a ticket via the web portal UI.
    """
    notes = "Resolved by Playwright browser automation test."
    res = resolve_ticket_in_browser("TICKET1024", notes=notes, portal_url=live_server)
    assert res["success"] is True
    assert res["finalStatus"] == "RESOLVED"
    assert "successfully marked as RESOLVED" in res["resultMessage"]
