# supplychain/services/uploads/product_bulk_upload.py

from decimal import Decimal, InvalidOperation
import pandas as pd

from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from django.db.models import Sum, Case, When, F, DecimalField, Value
from django.db.models.functions import Coalesce

from ...models import Product, UnitOfMeasure, Category, Supplier, StockTransaction

User = get_user_model()

# stock_level is REQUIRED (use 0 if you don’t want to set stock)
REQUIRED_COLS = {"name", "unit_cost", "uom_code", "stock_level"}
STOCK_COL = "stock_level"

DEC_OUT = DecimalField(max_digits=12, decimal_places=2)
DEC0 = Value(Decimal("0.00"), output_field=DEC_OUT)


def _norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def _split(cell):
    if pd.isna(cell) or cell is None:
        return []
    s = str(cell).strip()
    if not s:
        return []
    return [x.strip() for x in s.split(",") if x.strip()]


def _dec_required(cell, field):
    if pd.isna(cell) or str(cell).strip() == "":
        raise ValueError(f"'{field}' is required (use 0 if none)")
    try:
        return Decimal(str(cell).strip())
    except InvalidOperation:
        raise ValueError(f"'{field}' must be a valid number")


def _str_optional(cell):
    if pd.isna(cell) or cell is None:
        return ""
    return str(cell).strip()


def _norm_name(name: str) -> str:
    return " ".join((name or "").split()).strip()


def _row_context(row: pd.Series) -> str:
    name = _norm_name(_str_optional(row.get("name")))
    sku = _str_optional(row.get("sku"))
    uom_code = _str_optional(row.get("uom_code"))
    uom_name = _str_optional(row.get("uom_name"))
    stock_level = _str_optional(row.get("stock_level"))

    bits = []
    if name:
        bits.append(f"name='{name}'")
    if sku:
        bits.append(f"sku='{sku}'")
    if uom_code:
        bits.append(f"uom_code='{uom_code}'")
    if uom_name:
        bits.append(f"uom_name='{uom_name}'")
    if stock_level != "":
        bits.append(f"stock_level='{stock_level}'")
    return ", ".join(bits) if bits else "row details unavailable"


def _row_preview(row: pd.Series, max_fields: int = 10) -> dict:
    out = {}
    for k in list(row.index)[:max_fields]:
        v = row.get(k)
        if pd.isna(v):
            v = ""
        out[str(k)] = str(v).strip()
    return out


def _current_stock(product_id: int) -> Decimal:
    signed = Case(
        When(transaction_type=StockTransaction.RECEIVE, then=F("quantity")),
        When(transaction_type=StockTransaction.ISSUE, then=-F("quantity")),
        When(transaction_type=StockTransaction.ADJUST_IN, then=F("quantity")),
        When(transaction_type=StockTransaction.ADJUST_OUT, then=-F("quantity")),
        default=DEC0,
        output_field=DEC_OUT,
    )
    return (
        StockTransaction.objects
        .filter(product_id=product_id)
        .aggregate(q=Coalesce(Sum(signed), DEC0, output_field=DEC_OUT))["q"]
        or Decimal("0.00")
    )


def _get_or_create_uom(uom_code: str, uom_name: str | None):
    """
    Reconcile units by CODE first.

    Rules:
    - If code exists in DB: always reuse that row (single canonical UOM for that code).
      - If the file provides a name:
          - If DB name is a placeholder (same as code) and file name is nicer => update DB name.
          - Otherwise ignore the file name (do NOT try to create another UOM).
    - If code does not exist:
      - If file provides a name and that name is already used by some other code => fail with a clear message
        (because UnitOfMeasure.name is unique in your model).
      - Else create the new UOM.
    """
    uom_code = (uom_code or "").strip()
    uom_name = (uom_name or "").strip() or None

    existing_by_code = UnitOfMeasure.objects.filter(code=uom_code).first()
    if existing_by_code:
        # Optionally improve placeholder name
        if uom_name and existing_by_code.name.strip().lower() == uom_code.strip().lower():
            # Only update if it doesn't violate unique(name)
            if not UnitOfMeasure.objects.filter(name=uom_name).exclude(pk=existing_by_code.pk).exists():
                existing_by_code.name = uom_name
                existing_by_code.save(update_fields=["name"])
        return existing_by_code

    # code doesn't exist -> enforce unique(name)
    if uom_name:
        existing_by_name = UnitOfMeasure.objects.filter(name=uom_name).first()
        if existing_by_name and existing_by_name.code != uom_code:
            raise ValueError(
                f"Unit '{uom_name}' already exists in the system with code '{existing_by_name.code}'. "
                f"Your file uses code '{uom_code}'. Use the existing code '{existing_by_name.code}' "
                f"(or change the unit name)."
            )
        name_to_use = uom_name
    else:
        name_to_use = uom_code  # safe default

    return UnitOfMeasure.objects.create(code=uom_code, name=name_to_use)


def import_products_df(df: pd.DataFrame, *, actor=None, upload_id: int | None = None):
    if upload_id is None:
        raise ValueError("Internal error: upload reference is missing (upload_id).")

    df = _norm_cols(df)
    df = df.replace(r"^\s*$", pd.NA, regex=True)

    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError("Missing required column(s): " + ", ".join(sorted(missing)))

    created = 0
    updated = 0
    inventory_adjusted = 0
    errors = []

    for idx, row in df.iterrows():
        row_num = idx + 2

        try:
            with transaction.atomic():
                sku = _str_optional(row.get("sku")) or None

                name = _norm_name(_str_optional(row.get("name")))
                if not name:
                    raise ValueError("'name' cannot be blank")

                unit_cost = _dec_required(row.get("unit_cost"), "unit_cost")

                uom_code = _str_optional(row.get("uom_code"))
                if not uom_code:
                    raise ValueError("'uom_code' cannot be blank")

                target_stock = _dec_required(row.get(STOCK_COL), STOCK_COL)
                if target_stock < 0:
                    raise ValueError("'stock_level' cannot be negative")

                uom_name = _str_optional(row.get("uom_name")) or None
                uom = _get_or_create_uom(uom_code=uom_code, uom_name=uom_name)

                defaults = {
                    "name": name,
                    "description": _str_optional(row.get("description")),
                    "unit_cost": unit_cost,
                    "uom": uom,
                }

                # -----------------------------
                # PRODUCT DUPLICATE POLICY
                # -----------------------------
                # - If sku is provided: update/create by sku (this is the only "update" path).
                # - If sku is NOT provided:
                #     - If a product with same (name+uom) already exists => FAIL this row (no silent duplicates).
                #     - Else create.
                if sku:
                    product, was_created = Product.objects.update_or_create(sku=sku, defaults=defaults)
                else:
                    if Product.objects.filter(name__iexact=name, uom=uom).exists():
                        raise ValueError(
                            f"Product already exists for name '{name}' with unit '{uom.code}'. "
                            f"To update it, include the SKU in the spreadsheet. "
                            f"To create a new distinct item, change the name (e.g. include pack size)."
                        )
                    product = Product.objects.create(**defaults)
                    was_created = True

                if was_created:
                    created += 1
                else:
                    updated += 1

                # Optional lists
                cat_names = _split(row.get("categories"))
                if cat_names:
                    cats = [Category.objects.get_or_create(name=c)[0] for c in cat_names]
                    product.categories.set(cats)

                vendor_names = _split(row.get("vendors"))
                if vendor_names:
                    vends = [Supplier.objects.get_or_create(name=v)[0] for v in vendor_names]
                    product.vendors.set(vends)

                emails = _split(row.get("assigned_users"))
                if emails:
                    users = list(User.objects.filter(email__in=emails))
                    product.assigned_users.set(users)

                # Set stock via diff (idempotent per upload_id)
                cur = _current_stock(product.id)
                diff = target_stock - cur

                StockTransaction.objects.filter(
                    product=product,
                    source_type=StockTransaction.SRC_BULK_UPLOAD,
                    source_id=upload_id,
                ).delete()

                if diff > 0:
                    StockTransaction.objects.create(
                        product=product,
                        transaction_type=StockTransaction.ADJUST_IN,
                        quantity=diff,
                        source_type=StockTransaction.SRC_BULK_UPLOAD,
                        source_id=upload_id,
                        created_by=actor,
                        note=f"Bulk upload set stock: {cur} -> {target_stock}",
                    )
                    inventory_adjusted += 1
                elif diff < 0:
                    StockTransaction.objects.create(
                        product=product,
                        transaction_type=StockTransaction.ADJUST_OUT,
                        quantity=abs(diff),
                        source_type=StockTransaction.SRC_BULK_UPLOAD,
                        source_id=upload_id,
                        created_by=actor,
                        note=f"Bulk upload set stock: {cur} -> {target_stock}",
                    )
                    inventory_adjusted += 1

        except IntegrityError as e:
            errors.append({
                "row": row_num,
                "item": _row_context(row),
                "message": "This row could not be saved due to duplicate/conflicting data.",
                "details": str(e),
                "preview": _row_preview(row),
            })
        except Exception as e:
            errors.append({
                "row": row_num,
                "item": _row_context(row),
                "message": str(e),
                "details": "",
                "preview": _row_preview(row),
            })

    return {
        "created": created,
        "updated": updated,
        "inventory_adjusted": inventory_adjusted,
        "errors": errors,
    }
