# Kingfisher Supply Chain System

**Disclaimer:**  
This repository contains a public demonstration version of an internal business application.  
Certain modules, credentials, and proprietary configurations have been omitted or modified for security and privacy reasons.  
The production instance of this system is privately deployed and used by authorized personnel only.

---

## Overview

The **Kingfisher Supply Chain System** is a Django-based web application designed to improve procurement and inventory processes for small to medium-sized hospitality businesses.  
It provides a structured workflow that streamlines the movement of goods and approvals across departments, ensuring accountability, traceability, and operational efficiency.

---

## Core Features

- Role-based user management (Requester, Approver, Procurement Officer, Finance, Store)
- Multi-level requisition and purchase order approvals
- Supplier management and product cataloging
- Automated notifications (email and SMS)
- Purchase order generation and goods receipt verification
- Invoice tracking and payment processing
- Store issuance and minimum stock alerts
- Detailed activity logs and audit trails for transparency

---

## Technology Stack

| Component | Technology |
|------------|-------------|
| Backend | Django (Python) |
| Frontend | HTML, Tailwind CSS, JavaScript |
| Database | PostgreSQL |
| Notifications | SMTP (Email), Textbelt/Twilio (SMS) |
| Deployment | Docker-ready configuration |

---

## System Architecture

The system follows a modular design, separating procurement, inventory, and finance workflows into distinct Django apps.  
Environment-specific settings, credentials, and deployment scripts are not included in this repository.  

The following files and directories are excluded from version control using `.gitignore`:
