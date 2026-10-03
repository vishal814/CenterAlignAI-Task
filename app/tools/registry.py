import inspect
from typing import Dict, Any, Callable, List
from app.tools.customer_tools import search_customers, get_customer
from app.tools.ticket_tools import search_tickets, get_ticket, update_ticket, verify_ticket
from app.tools.payment_tools import get_payment, issue_refund, verify_refund
from app.tools.policy_tools import read_company_policy
from app.tools.browser_tools import inspect_ticket_in_browser, resolve_ticket_in_browser

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._descriptions: Dict[str, str] = {}
        self._register_default_tools()

    def register(self, name: str, func: Callable, description: str):
        self._tools[name] = func
        self._descriptions[name] = description

    def _register_default_tools(self):
        self.register(
            "search_customers",
            search_customers,
            "Search for customers by query string (name, email, or customer ID)."
        )
        self.register(
            "get_customer",
            get_customer,
            "Fetch detailed profile of a customer by customer_id."
        )
        self.register(
            "search_tickets",
            search_tickets,
            "Search support tickets by customer_id or issue description keyword."
        )
        self.register(
            "get_ticket",
            get_ticket,
            "Retrieve support ticket details by ticket_id."
        )
        self.register(
            "get_payment",
            get_payment,
            "Retrieve payment record and refund status by payment_id."
        )
        self.register(
            "read_company_policy",
            read_company_policy,
            "Read enterprise refund policy, eligibility rules, and approval thresholds."
        )
        self.register(
            "issue_refund",
            issue_refund,
            "Issue a refund for a payment. Fails safely on duplicate refunds or transient errors."
        )
        self.register(
            "update_ticket",
            update_ticket,
            "Update support ticket status (e.g. 'resolved', 'pending_approval') and append notes."
        )
        self.register(
            "verify_refund",
            verify_refund,
            "Independently verify in the database ledger that a refund was recorded and executed."
        )
        self.register(
            "verify_ticket",
            verify_ticket,
            "Independently verify that a ticket status in the database matches the expected status."
        )
        self.register(
            "inspect_ticket_in_browser",
            inspect_ticket_in_browser,
            "Automate Chromium browser using Playwright to inspect a support ticket in the web portal."
        )
        self.register(
            "resolve_ticket_in_browser",
            resolve_ticket_in_browser,
            "Automate Chromium browser using Playwright to submit a resolution for a ticket in the web portal."
        )

    def is_allowed(self, tool_name: str) -> bool:
        return tool_name in self._tools

    def get_tool_definitions_names(self) -> List[str]:
        return list(self._tools.keys())

    def execute(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        if not self.is_allowed(tool_name):
            return {
                "success": False,
                "error": f"Tool '{tool_name}' is not in the allowlisted tool registry. Allowed: {list(self._tools.keys())}"
            }
        func = self._tools[tool_name]
        try:
            # Filter kwargs to match function signature
            sig = inspect.signature(func)
            valid_args = {k: v for k, v in kwargs.items() if k in sig.parameters}
            return func(**valid_args)
        except Exception as e:
            return {
                "success": False,
                "error": f"Execution error in tool '{tool_name}': {str(e)}"
            }

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        defs = []
        for name, func in self._tools.items():
            sig = inspect.signature(func)
            params = {}
            for param_name, param in sig.parameters.items():
                params[param_name] = {
                    "type": str(param.annotation) if param.annotation != inspect.Parameter.empty else "str",
                    "default": str(param.default) if param.default != inspect.Parameter.empty else None
                }
            defs.append({
                "name": name,
                "description": self._descriptions.get(name, ""),
                "parameters": params
            })
        return defs

tool_registry = ToolRegistry()
