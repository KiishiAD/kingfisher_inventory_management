# supplychain/services/uploads/product_bulk_upload.py

from decimal import Decimal, InvalidOperation
import pandas as pd

from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from django.db.models import Sum, Case, When, F, DecimalField, Value
from django.db.models.functions import Coalesce

from ...models import Product, UnitOfMeasure, Category, Supplier, StockTransaction

User = get_user_model()

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
    # collapse whitespace + strip
    return " ".join((name or "").split()).strip()


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
    uom_name = (uom_name or "").strip()

    existing_by_code = UnitOfMeasure.objects.filter(code=uom_code).first()
    if existing_by_code:
        if uom_name and existing_by_code.name != uom_name:
            raise ValueError(
                f"Unit code '{uom_code}' already exists as '{existing_by_code.name}'. "
                f"File says '{uom_name}'. Fix the spreadsheet."
            )
        return existing_by_code

    if uom_name:
        existing_by_name = UnitOfMeasure.objects.filter(name=uom_name).first()
        if existing_by_name and existing_by_name.code != uom_code:
            raise ValueError(
                f"Unit name '{uom_name}' is already used by code '{existing_by_name.code}'. "
                f"File tries to use it for '{uom_code}'. Fix the spreadsheet."
            )
        name_to_use = uom_name
    else:
        name_to_use = uom_code

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

                uom_name = _str_optional(row.get("uom_name"))
                uom = _get_or_create_uom(uom_code=uom_code, uom_name=uom_name)

                defaults = {
                    "name": name,
                    "description": _str_optional(row.get("description")),
                    "unit_cost": unit_cost,
                    "uom": uom,
                }

                # ---- Identity rules ----
                # 1) If sku provided => update/create by sku
                # 2) Else => update/create by (name+uom) to prevent duplicates
                if sku:
                    product, was_created = Product.objects.update_or_create(sku=sku, defaults=defaults)
                else:
                    product = Product.objects.filter(name__iexact=name, uom=uom).first()
                    if product:
                        for k, v in defaults.items():
                            setattr(product, k, v)
                        product.save()
                        was_created = False
                    else:
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

        except IntegrityError:
            errors.append(
                f"Row {row_num}: Duplicate product detected (same name/unit) or another unique field conflict."
            )
        except Exception as e:
            errors.append(f"Row {row_num}: {e}")

    return {
        "created": created,
        "updated": updated,
        "inventory_adjusted": inventory_adjusted,
        "errors": errors,
    }
