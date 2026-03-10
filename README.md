# LoanTrack — IT Laptop Loan Management System

An internal web application for IT departments to manage laptop inventory and track employee loans.

---

## Table of Contents

- [Quick Start](#quick-start)
- [First Login](#first-login)
- [Features](#features)
- [How to Use](#how-to-use)
- [User Roles & Permissions](#user-roles--permissions)
- [Project Structure](#project-structure)
- [Database Schema](#database-schema)
- [API Reference](#api-reference)
- [Managing Users](#managing-users)
- [Exporting Data](#exporting-data)
- [Printing Labels](#printing-labels)
- [Production Tips](#production-tips)

---

## Quick Start

**Requirements:** Python 3.8 or later, Flask

```bash
# 1. Install Flask (skip if already installed)
pip install flask

# 2. Start the application
python app.py

# 3. Open in your browser
http://localhost:5000
```

The database (`laptop_loans.db`) is created automatically on first run. No other setup is needed.

---

## First Login

| Username | Password | Role |
|----------|----------|------|
| `admin`  | `admin`  | Superadmin |

> ⚠️ **Change the default password immediately** after first login.
> Go to **Users → Change Password** in the top section of the Users page.

---

## Features

**Inventory Management**
- Add laptops with brand, model, and serial number
- Asset numbers are generated automatically in the format `LAP-0001`, `LAP-0002`, etc.
- Edit or delete laptops at any time (cannot delete a laptop that is currently on loan)

**Loan Tracking**
- Create loan records linking a laptop to an employee
- Fields: employee ID, employee name, department, loan date, expected return date, reason
- Every loan records which user created it and when
- Visual overdue warning when expected return date has passed

**Return Processing**
- Mark a laptop as returned with a return date
- Add optional condition notes (e.g. scratches, missing accessories)
- Laptop automatically becomes available again upon return

**Search & Filters**
- Search by asset number, serial number, employee ID, or employee name
- Filter by: All / Active Loans / Returned

**Dashboard**
- Total laptops in inventory
- Currently loaned count
- Available count
- Overdue loans count
- Recent loan activity table

**Sticker Labels**
- Printable label for each laptop with asset number, serial number, and QR code
- Open from the 🏷️ button next to any laptop in the inventory page
- Print using Ctrl+P / Cmd+P in the browser

**CSV Export**
- Export full loan history to CSV
- Export full laptop inventory to CSV
- Available from the sidebar or the search bar on each page

---

## How to Use

### Adding a Laptop

1. Go to **Inventory**
2. Click **+ Add Laptop**
3. Fill in Brand, Model, and Serial Number (Purchase Date is optional)
4. Click **Add Laptop** — the system assigns the next available asset number automatically

### Creating a Loan

1. Go to **Loans**
2. Click **+ New Loan**
3. Enter the laptop's asset number (e.g. `LAP-0003`) — a live check will confirm if it is available
4. Fill in the employee details, dates, and reason
5. Click **Create Loan** — the laptop status changes to Loaned immediately

### Returning a Laptop

1. Go to **Loans**
2. Find the active loan and click **Return**
3. Confirm the return date and add any condition notes
4. Click **Confirm Return** — the laptop becomes available again

### Viewing Loan Details

Click the 👁 button on any loan row to see the full record including who created the loan and when.

---

## User Roles & Permissions

The system has three roles:

| Action | Superadmin | Admin | Viewer |
|--------|:----------:|:-----:|:------:|
| View dashboard & data | ✅ | ✅ | ✅ |
| View inventory & loans | ✅ | ✅ | ✅ |
| Print labels | ✅ | ✅ | ✅ |
| Export CSV | ✅ | ✅ | ✅ |
| Add / edit / delete laptops | ✅ | ✅ | ❌ |
| Create loans | ✅ | ✅ | ❌ |
| Process returns | ✅ | ✅ | ❌ |
| Delete loan records | ✅ | ❌ | ❌ |
| Manage users | ✅ | ❌ | ❌ |
| Change superadmin password | ✅ | ❌ | ❌ |

**Superadmin** is the master account. Only one exists and it cannot be deleted. It is the only account that can access the Users page, add/edit/delete users, and delete loan records.

**Admin** accounts are created by the superadmin. They can manage all day-to-day operations — adding laptops, creating loans, processing returns — but cannot touch user accounts or delete loan history.

**Viewer** accounts are read-only. Useful for managers or auditors who need to see data but should not make changes.

---

## Project Structure

```
laptop-loan-manager/
├── app.py               ← Flask application — all routes, API, and auth logic
├── laptop_loans.db      ← SQLite database (auto-created on first run)
├── README.md            ← This file
└── templates/
    ├── base.html        ← Shared layout, sidebar, navigation
    ├── login.html       ← Login page
    ├── dashboard.html   ← Overview with stats and recent activity
    ├── laptops.html     ← Inventory management page
    ├── loans.html       ← Loan tracking and return processing
    ├── users.html       ← User management (superadmin only)
    └── label.html       ← Printable sticker label with QR code
```

---

## Database Schema

### `users`

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| username | TEXT | Unique login name |
| password_hash | TEXT | SHA-256 hashed password |
| role | TEXT | `superadmin`, `admin`, or `viewer` |
| created_at | TEXT | Timestamp of account creation |

### `laptops`

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| asset_number | TEXT | Unique auto-generated ID, e.g. `LAP-0001` |
| brand | TEXT | e.g. HP, Dell, Lenovo, Apple |
| model | TEXT | e.g. EliteBook 840 G5 |
| serial_number | TEXT | Unique hardware serial number |
| purchase_date | TEXT | ISO date, optional |
| status | TEXT | `available` or `loaned` |
| notes | TEXT | Optional admin notes |
| created_at | TEXT | Timestamp added to system |

### `loans`

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| laptop_asset_number | TEXT | Foreign key → laptops.asset_number |
| employee_id | TEXT | e.g. EMP-001 |
| employee_name | TEXT | Full name of borrower |
| department | TEXT | Optional department |
| loan_date | TEXT | Date laptop was handed out |
| expected_return_date | TEXT | Agreed return date |
| return_date | TEXT | Actual return date, null if still on loan |
| reason | TEXT | Why the laptop was borrowed |
| status | TEXT | `loaned` or `returned` |
| condition_notes | TEXT | Notes recorded at return |
| created_by | TEXT | Username of who created the loan |
| created_at | TEXT | Timestamp the loan was created |

---

## API Reference

All endpoints require a valid login session. Endpoints marked `admin` require the Admin or Superadmin role. Endpoints marked `superadmin` require the Superadmin role only.

### Laptops

| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| GET | `/api/laptops` | All | List laptops. Supports `?q=` search and `?status=` filter |
| POST | `/api/laptops` | Admin | Add a new laptop |
| GET | `/api/laptops/:asset_number` | All | Get a single laptop |
| PUT | `/api/laptops/:asset_number` | Admin | Update laptop details |
| DELETE | `/api/laptops/:asset_number` | Admin | Delete a laptop (blocked if currently loaned) |

### Loans

| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| GET | `/api/loans` | All | List loans. Supports `?q=` search and `?status=` filter |
| POST | `/api/loans` | Admin | Create a new loan |
| POST | `/api/loans/:id/return` | Admin | Mark a loan as returned |
| DELETE | `/api/loans/:id` | Superadmin | Delete a loan record |

### Users

| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| POST | `/api/users` | Superadmin | Create a new user |
| PUT | `/api/users/:id` | Superadmin | Update role or password of a user |
| DELETE | `/api/users/:id` | Superadmin | Delete a user (cannot delete own account) |
| POST | `/api/users/change-password` | Superadmin | Change the superadmin's own password |

### Other

| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| GET | `/api/stats` | All | Returns total, loaned, available, overdue counts |
| GET | `/api/export/loans` | All | Download loan history as CSV |
| GET | `/api/export/inventory` | All | Download laptop inventory as CSV |

---

## Managing Users

All user management is done from the **Users** page, which is only visible when logged in as superadmin.

**Adding a user**
1. Click **+ Add User**
2. Enter username, password (minimum 6 characters), and select a role
3. Click **Create User**

**Editing a user**
1. Click **✏️ Edit** next to the user
2. Change the role and/or enter a new password
3. Leave the password blank to keep it unchanged
4. Click **Save Changes**

**Deleting a user**
1. Click **🗑️** next to the user
2. Confirm the deletion

**Changing the superadmin password**
1. Go to the **Users** page
2. Click **Change Password** in the superadmin card at the top
3. Enter the current password and the new password twice
4. Click **Update Password**

Alternatively, change it from the command line:

```bash
python3 -c "
import sqlite3, hashlib
conn = sqlite3.connect('laptop_loans.db')
new_hash = hashlib.sha256('your_new_password'.encode()).hexdigest()
conn.execute(\"UPDATE users SET password_hash=? WHERE username='admin'\", (new_hash,))
conn.commit()
print('Password updated')
"
```

---

## Exporting Data

Two CSV exports are available to all logged-in users:

- **Loan History CSV** — all loan records with employee details, dates, status, and condition notes
- **Inventory CSV** — all laptops with asset number, brand, model, serial number, and current status

Access them from:
- The **sidebar** (left navigation)
- The **⬇ Export CSV** button on the Inventory and Loans pages

---

## Printing Labels

Each laptop has a printable sticker label containing:
- Asset number (large, readable)
- Brand and model
- Serial number
- QR code encoding the asset number and serial number

To print a label:
1. Go to **Inventory**
2. Click the 🏷️ button on any laptop row
3. The label opens in a new tab
4. Press **Ctrl+P** (Windows/Linux) or **Cmd+P** (Mac)
5. Set paper size to match your label stock, or print on A4 and cut

---

## Production Tips

**Change the secret key** before deploying. Open `app.py` and replace:
```python
app.secret_key = 'it-laptop-manager-secret-2024'
```
with a long random string, for example generated by:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

**Run behind a reverse proxy** (nginx or Apache) with HTTPS enabled if the app will be accessed over a network.

**Back up the database regularly.** The entire system state lives in a single file:
```bash
cp laptop_loans.db laptop_loans_backup_$(date +%Y%m%d).db
```

**Load sample data for testing** using the included seed script:
```bash
python seed.py
```
This adds 8 sample laptops and several loan records so you can explore the system before adding real data. Do not run this on a live database.
