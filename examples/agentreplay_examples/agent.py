from typing import Any

from agentreplay import trace_agent, trace_llm, trace_tool


@trace_tool
def search_catalog(request: str) -> list[dict[str, Any]]:
    return [
        {"sku": "kb-01", "name": "Mechanical keyboard", "price": 89},
        {"sku": "kb-02", "name": "Compact keyboard", "price": 59},
    ]


@trace_tool
def check_inventory(sku: str, simulate_failure: bool = False) -> dict[str, Any]:
    if simulate_failure:
        raise ValueError("Inventory response is missing the required 'available' field")
    return {"sku": sku, "available": True, "quantity": 12}


@trace_llm(model="deterministic-fake-v1")
def compose_answer(request: str, products: list[dict[str, Any]], inventory: dict[str, Any]) -> str:
    product = products[0]
    return f"I recommend the {product['name']} for ${product['price']}. There are {inventory['quantity']} available."


@trace_agent(
    name="shopping-assistant",
    metadata={"model": "deterministic-fake-v1", "replay_target": "shopping-demo", "version": "1.0"},
)
def shopping_agent(request: str, simulate_failure: bool = False) -> str:
    products = search_catalog(request)
    inventory = check_inventory(products[0]["sku"], simulate_failure)
    return compose_answer(request, products, inventory)
