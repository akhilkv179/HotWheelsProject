# Hot Wheels Ecommerce Project

A Django-based ecommerce web application for browsing and purchasing Hot Wheels toy cars. The project includes customer-facing shopping features and an administrative interface for managing products, users, orders, and related operations.

**Project status:** Under active development.

## Technology Stack

- **Backend:** Python and Django
- **Database:** PostgreSQL
- **Frontend:** HTML, CSS, JavaScript, and Django templates
- **Version control:** Git and GitHub

## Project Structure

The project is organised into Django applications:

| Application | Responsibility |
|---|---|
| `accounts` | User accounts, authentication, OTP verification, profiles, and addresses |
| `admin_panel` | Administrative dashboard, user management, and reporting |
| `products` | Products, product variants, offers, and inventory |
| `categories` | Product categories and category offers |
| `cart` | Shopping cart and checkout |
| `orders` | Order processing, order history, cancellations, returns, and invoices |
| `wishlist` | Customer wishlist |
| `coupons` | Coupon-related functionality |
| `payments` | Payment-related functionality |
| `wallet` | Wallet-related functionality |
| `referrals` | Referral-related functionality |
| `reviews` | Product reviews |

The implementation and completion status of individual features may vary while development continues.

## Current Development Priorities

- Fix and test Google Sign-In (Google SSO).
- Implement authentication and role-based authorization for required APIs.
- Return appropriate HTTP status codes from API endpoints.
- Standardise URL paths to use hyphens instead of underscores.
- Improve product listing, sorting, product details, and availability handling.
- Prevent out-of-stock products from proceeding to checkout.
- Improve category sorting and blocked-product handling in the admin interface.
- Use Django Forms where appropriate for form-field validation.
- Add useful comments to views and improve automated testing.
- Maintain regular Git commits and push development work to GitHub.

## Local Development Setup

### 1. Clone the repository

```bash
git clone https://github.com/akhilkv179/HotWheelsProject.git
cd HotWheelsProject
```

### 2. Create and activate a virtual environment

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

Install the Python packages required by the project. A committed dependency manifest, such as `requirements.txt`, should be maintained so that a fresh environment can be reproduced reliably.

### 4. Configure PostgreSQL

Create a PostgreSQL database named `hotwheels`, or use the database name configured for your environment.

Configure the database connection and Django secret key using local settings or environment variables as appropriate. Do not commit passwords, API keys, OAuth client secrets, or production credentials.

### 5. Apply database migrations

```bash
python3 manage.py migrate
```

### 6. Create an administrator account

```bash
python3 manage.py createsuperuser
```

Follow the prompts to create the account.

### 7. Start the development server

```bash
python3 manage.py runserver
```

Open the local development address shown in the terminal.

**Note:** A fresh setup requires the project's dependencies and database configuration to be installed and completed first.

## Git Workflow

Use feature branches for separate tasks and commit changes regularly.

Suggested commit prefixes:

- `feat:` — new functionality
- `fix:` — bug fixes
- `docs:` — documentation changes
- `refactor:` — code restructuring without intended behaviour changes
- `test:` — tests and test-related changes
- `chore:` — maintenance and configuration

Example:

```bash
git add README.md
git commit -m "docs: add project README"
```

Review changes before committing and never push secrets or local environment files.

## Security and Contributions

Authentication, authorization, input validation, error handling, and stock consistency should be verified before deployment.

This project is intended for development and learning. Before production deployment, configure production-grade security, environment variables, static and media file handling, logging, database backups, and appropriate deployment infrastructure.
