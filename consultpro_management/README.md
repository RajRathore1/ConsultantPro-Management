# ConsultPro Management — Odoo 19 Module

**Industry-grade consulting firm management for Odoo 19.**

---

## Overview

ConsultPro Management is a complete end-to-end solution for consulting firms built natively on Odoo 19. It covers the full lifecycle: client acquisition → contracting → project delivery → timesheet approval → invoicing → KPI reporting.

---

## Module Structure

```
consultpro_management/
├── __init__.py
├── __manifest__.py
│
├── models/
│   ├── consultpro_client.py          # Client profiles, account management
│   ├── consultpro_contract.py        # Contracts, billing cycles, renewal
│   ├── consultpro_service.py         # Service catalog
│   ├── consultpro_service_line.py    # Contract service lines with pricing
│   ├── consultpro_project.py         # Projects linked to contracts
│   ├── consultpro_task.py            # Tasks with sub-tasks, deadlines
│   ├── consultpro_timesheet.py       # Timesheet logging & approval workflow
│   ├── consultpro_consultant.py      # Consultant profiles, utilization
│   ├── consultpro_invoice.py         # Invoice model + account.move extension
│   └── consultpro_dashboard.py       # KPI aggregation methods
│
├── services/
│   ├── consultpro_billing_service.py      # Invoice generation logic
│   ├── consultpro_project_service.py      # Project lifecycle business logic
│   └── consultpro_notification_service.py # Email notification orchestration
│
├── wizard/
│   ├── consultpro_invoice_wizard.py            # Timesheet-to-invoice wizard
│   ├── consultpro_timesheet_approval_wizard.py # Bulk approve/reject timesheets
│   └── consultpro_project_close_wizard.py      # Guided project closure
│
├── controllers/
│   ├── dashboard_controller.py     # JSON-RPC endpoints for OWL dashboard
│   └── client_portal_controller.py # Client self-service portal
│
├── views/                          # XML views for all models (form/list/kanban/search)
├── security/                       # Groups, record rules, ACLs
├── data/                           # Sequences, cron jobs, email templates, demo data
├── reports/                        # QWeb PDF reports (project, invoice, utilization)
└── tests/                          # Full integration test suite
```

---

## Features

### Client & Contract Management
- Client profiles with industry, rating, account manager
- Contract lifecycle: Draft → Sent → Approved → Active → Expired
- Auto-renewal, contract progress tracking, overdue detection
- Cron job for auto-expiry notifications (30 days / 7 days warning)

### Service Catalog
- Reusable services with hourly/daily/fixed/retainer billing types
- Service lines on contracts with quantity, unit price, discount, subtotal
- Link to Odoo product and analytic accounts

### Project Management
- Projects linked to clients and contracts
- KPI dashboard per project: completion %, budget spent, days remaining
- Health score engine (0–100) with risk flags
- Kanban board with color-coded urgency
- Project closure wizard with lessons-learned capture

### Task Management
- Tasks with sub-tasks, priorities, deadlines, acceptance criteria
- Kanban board grouped by status
- Overdue detection + visual badge warnings
- Full chatter and activity support

### Timesheet & Approval Workflow
- Consultants log time per project/task/activity type
- Submit → Approve/Reject flow
- Bulk approval wizard for managers
- Auto-sync approved timesheets to Odoo analytic lines
- Automated reminder cron for un-submitted entries

### Consultant Management
- Consultant profiles with seniority, skills, specializations
- Per-consultant billing rate and cost rate
- Real-time utilization rate (current month)
- Availability tracking: Available / Partially / Fully Booked / On Leave

### Invoicing
- One-click invoice generation from approved timesheets
- Group lines by consultant / task / activity type / single line
- Full timesheet breakdown attached to invoice
- Marks timesheets as "Invoiced" upon posting

### Reporting (PDF/QWeb)
- **Project Summary Report** — KPIs, team, tasks, timesheet totals
- **Invoice Report** — Professional invoice with timesheet breakdown
- **Consultant Utilization Report** — Per-consultant utilization with visual bar

### Client Portal
- Clients can view their projects, tasks, and invoices via Odoo portal
- Secure domain isolation (clients only see their own data)

### KPI Dashboard
- JSON-RPC API for OWL frontend component
- Revenue trend (6-month bar chart)
- Project status distribution (donut chart)
- Consultant utilization table
- Live activity feed

---

## Security Model

| Group | Access |
|---|---|
| Consultant | Own timesheets, assigned projects/tasks (read-only projects) |
| Project Manager | All projects, tasks, approve timesheets |
| Account Manager | Clients, contracts, invoice generation |
| Administrator | Full access |

---

## Installation

### Prerequisites
```
Odoo 19.0
Python 3.11+
```

### Required Odoo Modules (auto-resolved via `depends`)
```
base, mail, portal, project, hr, hr_timesheet,
account, sale_management, analytic, web
```

### Steps
1. Copy `consultpro_management/` to your Odoo addons directory
2. Restart Odoo server
3. Go to **Apps → Update Apps List**
4. Search for **ConsultPro Management** and click **Install**

---

## Running Tests

```bash
# Run all ConsultPro tests
python odoo-bin -d your_db --test-tags=consultpro --stop-after-init

# Run specific test class
python odoo-bin -d your_db --test-tags=consultpro/TestConsultingFlow --stop-after-init
```

---

## Key Workflows

### 1. Full Project Delivery Flow
```
Create Client → Create Contract → Add Service Lines →
Create Project → Assign Consultants → Create Tasks →
Log Timesheets → Submit → Manager Approves →
Generate Invoice (Wizard) → Post Invoice → Client Pays
```

### 2. Contract Renewal
```
Active Contract → action_renew() → New Draft Contract
(pre-filled with 1-year extension dates)
```

### 3. Project Health Monitoring
```
GET /consultpro/project/<id>/health
→ { score: 85, label: 'Healthy', flags: [] }
```

---

## Dashboard API Endpoints

| Endpoint | Description |
|---|---|
| `/consultpro/dashboard/kpis` | Top-level KPI cards |
| `/consultpro/dashboard/project_status` | Chart data by project state |
| `/consultpro/dashboard/revenue_trend` | Monthly revenue (last 6 months) |
| `/consultpro/dashboard/utilization` | Consultant utilization table |
| `/consultpro/dashboard/activity` | Recent activity feed |
| `/consultpro/project/<id>/health` | Per-project health score |
| `/consultpro/project/<id>/profitability` | Revenue vs cost breakdown |

---

## License

LGPL-3 — See [Odoo Community Edition License](https://www.gnu.org/licenses/lgpl-3.0.en.html)

---

## Author

**ConsultPro Team**
Built for Odoo 19 Community & Enterprise.