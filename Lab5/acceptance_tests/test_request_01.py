import pytest
from pydantic import ValidationError

from order_flow_service.src.models import OrderItem


def test_zero_quantity_is_rejected():
    with pytest.raises(ValidationError):
        OrderItem(
            sku="TEST-SKU",
            quantity=0,
            unit_price=10.0,
        )


def test_negative_quantity_is_rejected():
    with pytest.raises(ValidationError):
        OrderItem(
            sku="TEST-SKU",
            quantity=-1,
            unit_price=10.0,
        )


def test_positive_quantity_is_accepted():
    item = OrderItem(
        sku="TEST-SKU",
        quantity=1,
        unit_price=10.0,
    )

    assert item.quantity == 1