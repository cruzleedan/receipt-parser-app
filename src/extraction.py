"""Shared field contract and extraction instructions for every backend."""

from typing import Any, Dict

from src.models import ExtractionOptions

TOTAL_RULE = (
    "total is the final amount due for the purchase (the line labelled TOTAL, AMOUNT DUE or similar), "
    "not the cash tendered, the change, or the VATable or subtotal amount."
)
MERCHANT_RULE = "merchant_name is the store or business name at the top, not the address or the operator company."
# No example date: models copied the example into answers (WORK-0008).
DATE_RULE = "date is the transaction date copied exactly as printed on the receipt, including the year; do not reorder or convert it."
# WORK-0014: the code, not the symbol; a bare "$" is ambiguous and is cleaned to null in code.
CURRENCY_RULE = (
    "currency is the ISO 4217 code of the amounts, from a symbol or code printed on the receipt: PHP for ₱, P or PHP, "
    "USD only for US$ or USD; null when no currency is printed."
)

NUMBER = {"type": ["number", "null"]}
TEXT = {"type": ["string", "null"]}

# field -> (ExtractionOptions flag or None for always, JSON-schema type, NuExtract type)
FIELDS = {
    "merchant_name": (None, TEXT, "verbatim-string"),
    "merchant_address": ("merchant_address", TEXT, "verbatim-string"),
    "merchant_phone": ("merchant_phone", TEXT, "verbatim-string"),
    "date": ("date", TEXT, "verbatim-string"),
    "time": ("time", TEXT, "verbatim-string"),
    "subtotal": ("subtotal", NUMBER, "number"),
    "tax": ("tax", NUMBER, "number"),
    "tip": ("tip", NUMBER, "number"),
    "discount": ("discount", NUMBER, "number"),
    "total": (None, NUMBER, "number"),
    "currency": (None, TEXT, "verbatim-string"),
    "payment_method": ("payment_method", TEXT, "verbatim-string"),
    "card_last_4": ("payment_method", TEXT, "verbatim-string"),
    "receipt_number": ("receipt_number", TEXT, "verbatim-string"),
    "cashier": ("cashier", TEXT, "verbatim-string"),
}
ITEM_SCHEMA = {
    "type": "object",
    "properties": {"name": {"type": "string"}, "quantity": NUMBER, "unit_price": NUMBER, "total_price": NUMBER},
    "required": ["name", "quantity", "unit_price", "total_price"],
}
ITEM_TEMPLATE = {"name": "verbatim-string", "quantity": "number", "unit_price": "number", "total_price": "number"}


def wanted_fields(options: ExtractionOptions) -> list[str]:
    return [f for f, (flag, _, _) in FIELDS.items() if flag is None or getattr(options, flag)]


def json_schema(options: ExtractionOptions) -> Dict[str, Any]:
    """Every key required (null allowed): optional keys get skipped by models (WORK-0009)."""
    fields = wanted_fields(options)
    props = {f: FIELDS[f][1] for f in fields}
    if options.items:
        props["items"] = {"type": "array", "items": ITEM_SCHEMA}
    return {"type": "object", "properties": props, "required": list(props)}


def nuextract_template(options: ExtractionOptions) -> Dict[str, Any]:
    template = {f: FIELDS[f][2] for f in wanted_fields(options)}
    if options.items:
        template["items"] = [ITEM_TEMPLATE]
    return template


def generic_prompt(options: ExtractionOptions) -> str:
    fields = wanted_fields(options) + (["items (each: name, quantity, unit_price, total_price)"] if options.items else [])
    return (
        "Read this receipt and return its data as JSON with these fields: " + ", ".join(fields) + ".\n"
        f"- {MERCHANT_RULE}\n- {DATE_RULE}\n- {TOTAL_RULE}\n- {CURRENCY_RULE}\n"
        "Copy amounts as plain numbers without currency symbols. Use null for anything not printed. "
        "Return only the JSON."
    )

