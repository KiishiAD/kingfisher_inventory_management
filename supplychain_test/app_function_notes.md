## 1. App Function Recap

### Requisition & Approval
- **Requester** logs in and creates a **Requisition**:
  - Selects products + quantities
  - Marks as **urgent** (optional)
  - Uploads any **evidence** (file attachment)
- **Procurement (Mr. Monday)** sees a queue of **Pending Requisitions**:
  - Reviews each and chooses **Approve / Deny / Query**
  - Adds **notes** for context
  - **Notifications** go out on every status change
- When Procurement **approves**:
  - System **auto-generates** a **Purchase Order draft**
  - Notifies **“Mum”** for **final approval**

---

### Purchase Order & Approval
- **Mum** reviews the **PO lines**:
  - Chooses **Approve / Deny / Query**
- Once Mum **signs off**:
  - PO is marked **Sent**
  - System **emails** the Purchase Order to the **Supplier**

---

### Receiving & Invoice Processing
- **Receiving staff** view a list of **Sent POs**:
  - Record **actual quantities received**
  - Upload the **Supplier’s invoice PDF**
- **Accountant** reviews each **invoice line**:
  - Marks each line as **Approved / Query**
  - Adds **notes** if needed
  - **Partial approvals** or **queries** trigger re-notifications to Procurement and Mum
- **Mum** performs the final **“go/no-go”** on the invoice:
  - Chooses **Payment Type** (cheque vs. transfer)
  - Once approved, system **flags** the invoice **for payment**

---

### Payment
- **Accountant** uploads **payment proof** (scanned cheque image or bank-transfer receipt)
- Marks the **Payment record** as **Complete**

---

### Store Issuance
- **Store team** creates internal **IssuanceRequests** to draw stock for the **Kitchen**
- These requests follow the same **Approve / Deny / Query** cycle:
  - Includes **file-upload** of the physical **issue slip**

---

### Inventory & Alerts
- Every **receipt** or **issuance** creates a **StockTransaction**:
  - Enables the system to compute **real-time stock levels** by summing all transactions
- If a product’s stock dips below its configured **threshold**:
  - A **LowStockAlert** fires
  - The alert appears on **dashboards** until **acknowledged**

---

## 2. High-Level UI Suggestions

### A. Role-Based Dashboards
- Landing page after login shows a **summary card** for each role:
  - **Requester**:  
    - “My Open Requisitions”  
    - Button to **Create New Requisition**
  - **Procurement**:  
    - Counts of **Pending Reqs**, **Queried**, **Denied**
  - **Mum**:  
    - “POs Awaiting Approval”  
    - “Invoices Awaiting Final Sign-off”
  - **Receiving**:  
    - “Shipments to Receive”  
    - Quick-link to **Log Quantities**
  - **Accountant**:  
    - “Invoice Lines to Approve”  
    - “Payments to Process”
  - **Store**:  
    - “Internal Issuance Requests”  
    - “Low-Stock Alerts”

---

### B. Unified Navigation
- **Top navigation bar** with **Global Search** (search by Requisition #, PO #, Product SKU)
- **Side menu** grouping by function:  
  - **Master Data**  
  - **Requisition**  
  - **Purchase Orders**  
  - **Receiving**  
  - **Accounting**  
  - **Store Issuance**  
  - **Inventory**

---

### C. List & Detail Views
- **List pages** for each entity (Requisition, PO, etc.) should include:
  - **Togglable filters** (e.g., status, date range, requester)
  - **Column sorting** (e.g., most urgent first)
  - **Bulk-action checkboxes** (approve or deny multiple items at once)
- **Detail pages** use a **tabbed** or **accordion** layout to separate:
  1. **Header Info** (dates, status badges, core fields)
  2. **Line Items Table**
  3. **Audit Trail** (history of approvals/actions)
  4. **File-Upload / Attachments** section

---

### D. In-Context Actions & Modals
- Wherever users need to **Approve / Deny / Query**:
  - Use a small **modal dialog** letting them pick an action, add notes, and submit
  - Ensures users **don’t lose their place** on the page
- Display **status badges** prominently (e.g., red = **Denied**, yellow = **Queried**, green = **Approved**) next to each record

---

### E. Form Design
- **Multi-step wizard** for complex flows (e.g., creating a Requisition with many items):
  1. **Step 1** – Select Products  
  2. **Step 2** – Enter Quantities & Upload Evidence  
  3. **Step 3** – Review & Submit
- **Inline row editing** in line-item tables:
  - Allow users to **Tab** between quantity cells
  - Click “+ Add another line” **without leaving** the page

---

### F. Notifications & Alerts
- **In-app toast messages** on every status change (e.g., “Your Requisition was approved by Procurement”)
- **Real-time alert banner** or **sidebar widget** for **Low-Stock Alerts**, linking directly to the **Product detail**
- **Email/SMS integrations** for critical steps (e.g., “Mum, you have 5 invoices pending final sign-off”)

---

### G. Reporting & Analytics
- **Dashboard widget** showing:
  - **Top 5 low-stock products**
  - **Monthly purchase spend chart**
  - **Average approval turnaround times**
- **Drill-down tables** that can be **exported** to **CSV** or **PDF**

---

### H. Consistent Design System
- Use a **Component Library** (cards, tables, forms, modals) for consistency
- **Color-code statuses** across the app:
  - Green = **Approved**
  - Amber = **Queried**
  - Red = **Denied**
- Ensure **mobile responsiveness** for on-the-floor receiving or approvals on tablets
