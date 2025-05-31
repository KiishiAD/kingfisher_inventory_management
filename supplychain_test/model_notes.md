## Master Data

### UnitOfMeasure
Holds units like **kg**, **L**, **pack**—so every product’s quantity can be interpreted correctly.

### Category
Groups products (cold, dry, drinks, bar, etc.) for filtering and reporting.

### Supplier
Vendors you purchase from, including contact details.

### Product
Your catalog item, comprising:
- **SKU**
- **Name**
- **Cost**
- **Unit of Measure (UoM)**
- **Categories**
- **Vendors**
- Any assigned users responsible for it

---

## Requisition & Approval

### Requisition
The “header” for a user’s request. Tracks:
- **Requester**
- **Status** (pending / approved / denied / queried)
- **Evidence Attachment** (file uploads, scanned documents)
- **Urgent Flag**

### RequisitionItem
Each line on the requisition:
- **Product** (reference to a `Product` in Master Data)
- **Quantity** (number of units requested)

### RequisitionApproval
Audit trail of every approval action:
- **Who** approved / denied / queried
- **When** (timestamp of action)
- **Notes** (any additional commentary)

---

## Purchase Order (PO) & Approval

### PurchaseOrder
Generated from an approved requisition (or created directly). Contains:
- **Link to Supplier** (reference to a `Supplier`)

