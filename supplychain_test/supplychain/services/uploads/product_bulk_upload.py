from decimal import Decimal, InvalidOperation
import pandas as pd

from django.contrib.auth import get_user_model
from django.db import transaction

from ...models import Product, UnitOfMeasure, Category, Supplier

User = get_user_model()

REQUIRED_COLS = {"name", "unit_cost", "uom_code"}  # sku optional for "create"; required for "update"

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

def _dec(cell, field):
    if pd.isna(cell) or str(cell).strip() == "":
        raise ValueError(f"{field} is required")
    try:
        return Decimal(str(cell).strip())
    except InvalidOperation:
        raise ValueError(f"{field} is not a valid number")

@transaction.atomic
def import_products_df(df: pd.DataFrame):
    df = _norm_cols(df)

    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    created = 0
    updated = 0
    errors = []

    # treat empty strings as NaN for consistent checks
    df = df.replace(r"^\s*$", pd.NA, regex=True)

    for idx, row in df.iterrows():
        row_num = idx + 2  # header row is 1
        try:
            sku = row.get("sku")
            sku = None if pd.isna(sku) else str(sku).strip()

            name = str(row["name"]).strip()
            unit_cost = _dec(row["unit_cost"], "unit_cost")
            uom_code = str(row["uom_code"]).strip()

            if not name:
                raise ValueError("name cannot be blank")
            if not uom_code:
                raise ValueError("uom_code cannot be blank")

            # optional: uom_name column
            uom_name = row.get("uom_name")
            uom_name = None if pd.isna(uom_name) else str(uom_name).strip()

            uom, _ = UnitOfMeasure.objects.get_or_create(
                code=uom_code,
                defaults={"name": uom_name or uom_code},
            )
            # if name provided and existing name is placeholder, you can update it
            if uom_name and uom.name == uom_code:
                uom.name = uom_name
                uom.save(update_fields=["name"])

            defaults = {
                "name": name,
                "description": "" if pd.isna(row.get("description")) else str(row.get("description")).strip(),
                "unit_cost": unit_cost,
                "uom": uom,
            }

            # UPDATE path: sku provided -> update_or_create
            if sku:
                product, was_created = Product.objects.update_or_create(sku=sku, defaults=defaults)
                if was_created:
                    created += 1
                else:
                    updated += 1
            else:
                # CREATE path: no sku -> create new product (your model should auto-generate sku OR you set it elsewhere)
                product = Product.objects.create(**defaults)
                created += 1

            # categories (comma separated)
            cat_names = _split(row.get("categories"))
            if cat_names:
                cats = [Category.objects.get_or_create(name=c)[0] for c in cat_names]
                product.categories.set(cats)

            # vendors (comma separated)
            vendor_names = _split(row.get("vendors"))
            if vendor_names:
                vends = [Supplier.objects.get_or_create(name=v)[0] for v in vendor_names]
                product.vendors.set(vends)

            # assigned_users (comma separated emails)
            emails = _split(row.get("assigned_users"))
            if emails:
                users = list(User.objects.filter(email__in=emails))
                product.assigned_users.set(users)

        except Exception as e:
            errors.append(f"Row {row_num}: {e}")

    return {"created": created, "updated": updated, "errors": errors}
