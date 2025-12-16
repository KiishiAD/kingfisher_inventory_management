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
        return render(request, self.template_name, {
            "form": ProductBulkUploadForm(),
            "section": "operations",
        })

    def post(self, request):
        form = ProductBulkUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "section": "operations"})

        f = form.cleaned_data["file"]
        filename = (f.name or "").lower()

        try:
            if filename.endswith(".csv"):
                df = pd.read_csv(f)
            elif filename.endswith(".xlsx") or filename.endswith(".xls"):
                df = pd.read_excel(f)
            else:
                raise ValueError("Upload a .csv or .xlsx file")

            result = import_products_df(df)

            messages.success(request, f"Created: {result['created']} | Updated: {result['updated']}")
            if result["errors"]:
                messages.warning(request, f"{len(result['errors'])} row(s) failed. See below.")

            return render(request, self.template_name, {
                "form": ProductBulkUploadForm(),
                "result": result,
                "section": "operations",
            })

        except Exception as e:
            messages.error(request, str(e))
            return render(request, self.template_name, {"form": form, "section": "operations"})
