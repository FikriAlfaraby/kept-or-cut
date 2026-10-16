"""A small order pipeline, used as a fixture: running it with a planted bug gives a real Python traceback."""

PRICES = {"kaos-hitam-l": 85000, "kemeja-putih-m": 145000, "celana-jeans-32": 210000}


def line_total(item: dict) -> int:
    return PRICES[item["sku"]] * item["qty"]


def order_total(order: dict) -> int:
    return sum(line_total(item) for item in order["items"])


def invoice(order: dict) -> str:
    return f"Order {order['id']}: Rp{order_total(order):,}"


def main() -> None:
    orders = [
        {"id": "INV-1041", "items": [{"sku": "kaos-hitam-l", "qty": 2}]},
        {
            "id": "INV-1042",
            "items": [{"sku": "kemeja-putih-m", "qty": 1}, {"sku": "celana-jeans-32", "qty": 1}],
        },
    ]
    for order in orders:
        print(invoice(order))


if __name__ == "__main__":
    main()
