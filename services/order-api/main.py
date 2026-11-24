"""
order-api (Service A) — point d'entrée POST /order.

Contrainte du TP : AUCUNE bibliothèque d'observabilité (ni prometheus-client,
ni SDK OpenTelemetry). Toute la télémétrie est extraite par Grafana Beyla (eBPF).
"""
import os
import uuid

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

PRICING_URL = os.getenv("PRICING_URL", "http://pricing-engine:8080/price")
TIMEOUT_S = float(os.getenv("PRICING_TIMEOUT_S", "10"))

app = FastAPI(title="order-api")
client: httpx.AsyncClient | None = None


class OrderItem(BaseModel):
    sku: str = Field(min_length=1)
    quantity: int = Field(gt=0, le=1000)


class Order(BaseModel):
    customer_id: str = Field(min_length=1)
    items: list[OrderItem] = Field(min_length=1)


@app.on_event("startup")
async def startup() -> None:
    global client
    client = httpx.AsyncClient(
        timeout=TIMEOUT_S,
        limits=httpx.Limits(max_connections=500, max_keepalive_connections=200),
    )


@app.on_event("shutdown")
async def shutdown() -> None:
    await client.aclose()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/order")
async def create_order(order: Order):
    # 1) Validation (faite par pydantic) + calcul local de la quantité totale
    total_qty = sum(i.quantity for i in order.items)

    # 2) Appel synchrone HTTP vers le microservice B (pricing-engine)
    try:
        resp = await client.get(
            PRICING_URL,
            params={"sku": order.items[0].sku, "qty": total_qty},
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=504, detail=f"pricing-engine unreachable: {exc}")

    if resp.status_code >= 500:
        # Propagation de l'erreur amont : A renvoie 502 Bad Gateway
        return JSONResponse(
            status_code=502,
            content={"error": "pricing-engine failure", "upstream_status": resp.status_code},
        )

    price = resp.json()

    # 3) Consolidation et réponse
    return {
        "order_id": str(uuid.uuid4()),
        "customer_id": order.customer_id,
        "items": len(order.items),
        "total_quantity": total_qty,
        "unit_price": price["unit_price"],
        "total_price": round(price["unit_price"] * total_qty, 2),
        "currency": price["currency"],
        "status": "CONFIRMED",
    }
