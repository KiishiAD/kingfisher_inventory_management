# supplychain/views/operations_views.py  (ProductBulkUploadView)

import time
import pandas as pd

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import render
from django.views import View

from ..forms import ProductBulkUploadForm
from ..services.uploads.product_bulk_upload import import_products_df


class ProductBulkUploadView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "supplychain.bulk_upload_products"
    raise_exception = True
    template_name = "supplychain/operations/product_bulk_upload.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {"form": ProductBulkUploadForm(), "section": "operations"},
        )

    def post(self, request):
        form = ProductBulkUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, "Please choose a file to upload.")
            return render(
                request,
                self.template_name,
                {"form": form, "section": "operations"},
            )

        f = form.cleaned_data["file"]
        original_name = (f.name or "").strip()
        filename = original_name.lower()

        try:
            if filename.endswith(".csv"):
                df = pd.read_csv(f)
            elif filename.endswith(".xlsx") or filename.endswith(".xls"):
                df = pd.read_excel(f)
            else:
                messages.error(request, "Unsupported file type. Please upload an Excel (.xlsx) or CSV (.csv) file.")
                return render(
                    request,
                    self.template_name,
                    {"form": form, "section": "operations"},
                )

            # One reference number for the whole upload; stored on StockTransaction.source_id
            upload_id = int(time.time() * 1000)

            result = import_products_df(df, actor=request.user, upload_id=upload_id)

            created = result.get("created", 0)
            updated = result.get("updated", 0)
            inventory_adjusted = result.get("inventory_adjusted", 0)
            errors = result.get("errors") or []

            if errors:
                # Non-programmer friendly summary
                messages.warning(
                    request,
                    (
                        f"Upload completed with some issues. "
                        f"Created: {created}, Updated: {updated}, Stock updated: {inventory_adjusted}. "
                        f"{len(errors)} row(s) could not be processed."
                    ),
                )
            else:
                messages.success(
                    request,
                    (
                        f"Upload successful. "
                        f"Created: {created}, Updated: {updated}, Stock updated: {inventory_adjusted}."
                    ),
                )

            return render(
                request,
                self.template_name,
                {
                    "form": ProductBulkUploadForm(),
                    "result": result,
                    "upload_id": upload_id,
                    "uploaded_filename": original_name,
                    "section": "operations",
                },
            )

        except Exception as e:
            messages.error(request, f"Upload failed: {e}")
            return render(
                request,
                self.template_name,
                {"form": form, "section": "operations"},
            )
