# SupplyWise — Logistics & Supply Chain Management System

SupplyWise is a role-based logistics and supply chain web application built with Flask, MySQL, and MongoDB. It manages inventory, cart selections, checkouts, automatic transporter assignment, invoice generation, feedback, and real-time notification alerts.

---

## 🏗️ Architecture & Interaction Diagram

```text
 +---------------------------------------------------------------------------------+
 |                                   CLIENT WEB BROWSER                            |
 |  (Dashboards: Admin, Customer, Retailer, Supplier, Transporter, Cart, Payment)  |
 +---------------------------------------------------------------------------------+
                                       ▲         │
                           HTTP / HTML |         │ HTTP POST / Form Submission
                                       │         ▼
 +---------------------------------------------------------------------------------+
 |                                FLASK WEB APP (app.py)                           |
 |                - Routing, Controllers & Business Logic                          |
 |                - Session Management & User Authentication                       |
 |                - PDF Invoice & Report Generation (reportlab)                    |
 +---------------------------------------------------------------------------------+
                                       │         │
                   SQL Queries (mysql) |         │ NoSQL Operations (pymongo)
                                       ▼         ▼
 +----------------------------------------+   +------------------------------------+
 |             MYSQL DATABASE             |   |          MONGODB DATABASE          |
 |     - Users & Roles (customer, etc)    |   |     - Notifications Collection     |
 |     - Products & Inventory Table       |   |       (Stores asynchronous activity|
 |     - Relational Transactions          |   |        alerts for users)           |
 |     - Feedback, Admin Logs, Invoices   |   |                                    |
 +----------------------------------------+   +------------------------------------+
```

---

## 🛠️ Tech Stack Reference

| Technology | Category | Purpose / Description |
| :--- | :--- | :--- |
| **Python** | Programming Language | Core backend scripting language |
| **Flask** | Web Framework | Lightweight micro-framework for web application structure and routing |
| **MySQL** | Relational Database | Relational storage for users, inventory, invoices, and transactions |
| **MongoDB** | Document Database | Storage of real-time user-targeted notifications and logs |
| **ReportLab** | PDF Library | Dynamically generates downloadable PDF invoices and sales reports |
| **PyMongo** | DB Client Library | MongoDB connection driver for Python |
| **MySQL Connector** | DB Client Library | MySQL connection driver for Python |
| **python-dotenv** | Library | Loads credentials securely from `.env` files into environment variables |

---

## 🌟 Core Features

- **Multi-Role Authentication**: Customized dashboards and functionality for **Admin**, **Customer**, **Retailer**, **Supplier**, and **Transporter**.
- **Inventory & Pricing Controls**: Suppliers and Retailers can manage their inventory lists, update stock quantities, and adjust product pricing.
- **Cart & Checkout Flow**: Customers and Retailers can search and add available products from their preceding chain links to their shopping carts and place orders.
- **Transporter Auto-Assignment**: Orders are automatically assigned to the transporter with the lowest workload (delivery count) for execution.
- **PDF Document Generation**: Generates clean, downloadable PDF files on-the-fly for invoices and sales reports using ReportLab.
- **Notifications System**: Powered by MongoDB to store and display activity alerts and transactions asynchronously.

---

## 📋 Environment Variables Reference

Create a local `.env` configuration file in the project root folder. Use the following environment variables:

| Variable Name | Required | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `FLASK_APP` | No | `app.py` | Main application entry point |
| `FLASK_ENV` | No | `development` | Environment mode (`development` or `production`) |
| `FLASK_DEBUG` | No | `True` | Runs Flask in debug hot-reloaded mode if set to `True` |
| `FLASK_SECRET_KEY` | Yes | `your_secret_key` | Secret key used for signing session cookies securely |
| `DB_HOST` | Yes | `localhost` | Host address of the MySQL database |
| `DB_USER` | Yes | `root` | Username for MySQL authentication |
| `DB_PASSWORD` | Yes | *None* | Password for MySQL authentication |
| `DB_NAME` | Yes | `wms` | Target MySQL database schema name |
| `MONGO_URI` | Yes | `mongodb://localhost:27017/` | Connection URI for the MongoDB server |
| `UPI_ID` | Yes | `your_upi_id_here@bank` | Target merchant UPI payment address for QR code payments |

---

## 🚀 Setup & Installation Instructions

Follow these step-by-step instructions to get the application running locally:

### 1. Prerequisite Installations
Ensure you have the following installed on your machine:
- [Python 3.10+](https://www.python.org/downloads/)
- [MySQL Server](https://dev.mysql.com/downloads/installer/)
- [MongoDB Community Server](https://www.mongodb.com/try/download/community)

### 2. Clone and Navigate to Directory
```bash
git clone <your-repository-url>
cd SupplyWise
```

### 3. Initialize python Virtual Environment
Create a clean local virtual environment and activate it:
```bash
# On Windows
python -m venv venv
.\venv\Scripts\activate

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Setup Databases
- **MySQL Configuration**:
  1. Open your MySQL client and run the SQL schema file to create the tables.
  2. Create a database named `wms`.
- **MongoDB Configuration**:
  1. Ensure MongoDB service is running on `localhost:27017`.
  2. The application will automatically create the database `wms_db` and collection `notifications` on first launch.

### 6. Create Environment File
Copy the example environment template and fill in your local credentials:
```bash
cp .env.example .env
```
Open the `.env` file and replace:
- `DB_USER` and `DB_PASSWORD` with your MySQL server credentials.
- `UPI_ID` with your merchant UPI address.
- `FLASK_SECRET_KEY` with a strong random string.

### 7. Run the Application
Start the Flask local development server:
```bash
python app.py
```
Open your browser and navigate to `http://127.0.0.1:5000/`.

---

## 📂 Project Directory Structure

```text
SupplyWise/
├── .env                         # Local environment settings containing secrets (IGNORED BY GIT)
├── .env.example                 # Template file showing required configurations
├── .gitignore                   # Files and directories ignored by Git
├── README.md                    # Professional project documentation (this file)
├── app.py                       # Main backend application logic and routes
├── requirements.txt             # Project package dependencies
├── static/                      # Static assets (images, stylesheets, scripts)
│   └── .gitkeep                 # Ensures empty folder structure is tracked by Git
└── templates/                   # HTML UI pages and Dashboards
    ├── admin_dashboard.html
    ├── cart.html
    ├── customer_dashboard.html
    ├── index.html
    ├── login.html
    ├── payment.html
    ├── register.html
    ├── retailer_dashboard.html
    ├── supplier_dashboard.html
    └── transporter_dashboard.html
```
