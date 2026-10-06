"""
app/ai/tools/inventory_tools.py
===============================
Concrete AI tools for inventory and ordering.

These are the actual capabilities the AI workforce uses to:
- create orders automatically from inbound customer inquiries
- trigger purchase orders when stock is below threshold
- update inventory counts
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import TenantContext
from app.core.money import Money
from app.db.types import round_money
from app.models.customer import Customer
from app.models.inventory import Inventory, InventoryMovement
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem
from app.models.supplier import SupplierProduct
from app.ai.tools.base import AITool, ToolResult
from app.services.exchange_rate_service import CurrencyService


class CreateOrderFromInquiryTool(AITool):
    """
    Automatically creates an order from a customer inquiry.
    Requires approval when the order total exceeds a threshold.
    """

    name = "create_order_from_inquiry"
    requires_approval = True
    required_permission = "orders.create"

    APPROVAL_THRESHOLD = Decimal("1000")  # in org base currency

    def execute(self, db: Session, ctx: TenantContext, parameters: dict) -> ToolResult:
        if not self._check_permission(ctx):
            return ToolResult(False, {}, error="Permission denied: orders.create")

        required = ("customer_id", "items")
        for k in required:
            if k not in parameters:
                return ToolResult(False, {}, error=f"Missing parameter: {k}")

        customer = db.get(Customer, parameters["customer_id"])
        if not customer or customer.organization_id != ctx.organization_id:
            return ToolResult(False, {}, error="Customer not found in this organization")

        # Resolve products + validate stock
        line_items: list[tuple[Product, int, Decimal]] = []
        subtotal = Decimal("0")
        for item in parameters["items"]:
            product = db.get(Product, item["product_id"])
            if not product or product.organization_id != ctx.organization_id:
                return ToolResult(False, {}, error=f"Product not found: {item['product_id']}")
            qty = int(item["quantity"])
            if qty <= 0:
                return ToolResult(False, {}, error="Quantity must be positive")
            if not product.inventory or product.inventory.quantity_available < qty:
                return ToolResult(False, {}, error=f"Insufficient stock for {product.name}")
            line_items.append((product, qty, product.price))
            subtotal += product.price * qty

        # Currency logic — order placed in organization's base currency by default
        from app.models.organization import Organization
        org = db.get(Organization, ctx.organization_id)
        if not org:
            return ToolResult(False, {}, error="Organization not found")

        currency = org.base_currency
        tax_rate = Decimal(str(org.tax_rate_pct)) / Decimal("100")
        tax = (subtotal * tax_rate)
        total = subtotal + tax

        # Generate order number
        order_number = f"AI-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{customer.id[:8]}"

        order = Order(
            organization_id=ctx.organization_id,
            order_number=order_number,
            customer_id=customer.id,
            status="PENDING",
            currency=currency,
            subtotal=subtotal,
            discount=Decimal("0"),
            tax=tax,
            total_amount=total,
            base_currency=currency,
            exchange_rate=Decimal("1"),
            base_amount=total,
            placed_by_agent_id=ctx.agent_id,
            placed_by_user_id=ctx.actor_user_id,
        )
        db.add(order)
        db.flush()

        for product, qty, price in line_items:
            db.add(OrderItem(
                organization_id=ctx.organization_id,
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,
                quantity=qty,
                unit_price=price,
                line_total=price * qty,
                unit_cost=product.cost,
            ))
            # Reserve inventory
            if product.inventory:
                product.inventory.quantity_reserved += qty
                product.inventory.quantity_available -= qty

        # Approval gate
        needs_approval = total >= self.APPROVAL_THRESHOLD

        self._audit(db, ctx, parameters, ToolResult(True, {"order_id": order.id, "order_number": order_number, "needs_approval": needs_approval}))
        db.commit()

        return ToolResult(
            success=True,
            output={
                "order_id": order.id,
                "order_number": order_number,
                "total": str(total),
                "currency": currency,
                "needs_approval": needs_approval,
            },
            requires_approval=needs_approval,
        )


class TriggerRestockOrderTool(AITool):
    """
    When a product is out of stock (or below reorder threshold), create a
    draft purchase order from the cheapest supplier.
    """

    name = "trigger_restock_order"
    requires_approval = True
    required_permission = "orders.create"

    def execute(self, db: Session, ctx: TenantContext, parameters: dict) -> ToolResult:
        if not self._check_permission(ctx):
            return ToolResult(False, {}, error="Permission denied: orders.create")

        product_id = parameters.get("product_id")
        if not product_id:
            return ToolResult(False, {}, error="Missing product_id")
        product = db.get(Product, product_id)
        if not product or product.organization_id != ctx.organization_id:
            return ToolResult(False, {}, error="Product not found")

        # Check inventory
        if not product.inventory or product.inventory.quantity_on_hand > product.reorder_threshold:
            return ToolResult(True, {"skipped": True, "reason": "Stock above threshold"})

        # Find supplier
        supplier_product = db.execute(
            select(SupplierProduct)
            .where(SupplierProduct.product_id == product.id)
            .order_by(SupplierProduct.supplier_price.asc())
        ).scalars().first()
        if not supplier_product:
            return ToolResult(False, {}, error="No supplier configured for this product")

        # Determine quantity to restock (min order qty or 2x threshold)
        restock_qty = max(supplier_product.min_order_qty, product.reorder_threshold * 2)
        line_total = supplier_product.supplier_price * restock_qty

        from app.models.organization import Organization
        org = db.get(Organization, ctx.organization_id)
        po_number = f"PO-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{product.id[:8]}"

        po = PurchaseOrder(
            organization_id=ctx.organization_id,
            po_number=po_number,
            supplier_id=supplier_product.supplier_id,
            status="DRAFT",
            currency=org.base_currency,
            total_amount=line_total,
            base_currency=org.base_currency,
            exchange_rate=Decimal("1"),
            base_amount=line_total,
            created_by_agent_id=ctx.agent_id,
            created_by_user_id=ctx.actor_user_id,
        )
        db.add(po)
        db.flush()
        db.add(PurchaseOrderItem(
            organization_id=ctx.organization_id,
            purchase_order_id=po.id,
            product_id=product.id,
            product_name=product.name,
            quantity=restock_qty,
            unit_price=supplier_product.supplier_price,
            line_total=line_total,
        ))

        self._audit(db, ctx, parameters, ToolResult(True, {"purchase_order_id": po.id, "po_number": po_number}))
        db.commit()

        return ToolResult(
            success=True,
            output={"purchase_order_id": po.id, "po_number": po_number, "quantity": restock_qty, "total": str(line_total)},
            requires_approval=True,
        )


class UpdateInventoryTool(AITool):
    """Adjust inventory count (e.g. after stock count)."""

    name = "update_inventory"
    requires_approval = False
    required_permission = "inventory.update"

    def execute(self, db: Session, ctx: TenantContext, parameters: dict) -> ToolResult:
        if not self._check_permission(ctx):
            return ToolResult(False, {}, error="Permission denied: inventory.update")

        product_id = parameters.get("product_id")
        new_qty = parameters.get("quantity_on_hand")
        if not product_id or new_qty is None:
            return ToolResult(False, {}, error="Missing product_id or quantity_on_hand")

        product = db.get(Product, product_id)
        if not product or product.organization_id != ctx.organization_id:
            return ToolResult(False, {}, error="Product not found")

        inv = product.inventory
        if not inv:
            inv = Inventory(
                organization_id=ctx.organization_id,
                product_id=product.id,
                quantity_on_hand=0,
                quantity_reserved=0,
                quantity_available=0,
            )
            db.add(inv)
            db.flush()

        old_qty = inv.quantity_on_hand
        delta = int(new_qty) - old_qty
        inv.quantity_on_hand = int(new_qty)
        inv.quantity_available = inv.quantity_on_hand - inv.quantity_reserved

        db.add(InventoryMovement(
            organization_id=ctx.organization_id,
            inventory_id=inv.id,
            product_id=product.id,
            movement_type="ADJUSTMENT",
            quantity_change=delta,
            quantity_after=inv.quantity_on_hand,
            reference="ai_update_inventory",
            actor_id=ctx.actor_user_id,
        ))

        self._audit(db, ctx, parameters, ToolResult(True, {"product_id": product_id, "new_qty": new_qty}))
        db.commit()

        return ToolResult(True, output={"product_id": product_id, "new_quantity_on_hand": inv.quantity_on_hand, "delta": delta})
