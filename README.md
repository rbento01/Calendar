# 📅 Calendar App

A Flask-based calendar application that supports **LDAP and local authentication**, **team-based scheduling**, and **vacation approval workflows**.

This README describes the **standard  version** of the application, suitable for **Windows and Linux** environments.

---

## ✨ Features

* 🔐 **Authentication**

  * Login using **LDAP** or **local accounts**
  * Role-based access (User / Manager / Admin)

* 👥 **Teams**

  * Users belong to a team
  * Events can be created **for yourself or for your team**

* 📆 **Calendar & Events**

  * Schedule **meetings** and **vacations**
  * View all approved events in a shared calendar

* 🏖️ **Vacation Approval Flow**

  * Vacation requests start as **Pending**
  * **Managers/Admins** can approve or reject
  * Users see the vacation status directly on the calendar via **color coding**

---

## 🧱 Tech Stack

* Python 3.10+
* Flask 3.x
* Flask-Login
* Flask-SQLAlchemy
* Flask-WTF
* SQLAlchemy 2.x
* SQLite
* LDAP (via ldap3 / flask-ldap3-login, optional)
* Bootstrap + FullCalendar

---

## 📋 Requirements

* Python **3.10 or newer**
* Git
* Virtual environment support (venv)
* (Optional) Access to an LDAP server

---

## 📥 Clone the Repository

```bash
git clone https://github.com/rbento01/Calendar.git
cd Calendar
```

---

## 🐍 Set Up a Virtual Environment (Recommended)

### Windows (PowerShell)

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 📦 Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 🔐 Environment Configuration (`.env`)

The application requires a `.env` file for configuration.

Create a `.env` file in the **project root**:

```env
# Flask / SQLAlchemy
FLASK_SECRET_KEY=your_secret_key_here
SQLALCHEMY_DATABASE_URI=sqlite:///instance/calendar.db
SQLALCHEMY_TRACK_MODIFICATIONS=False

# LDAP (optional)
LDAP_SERVER=ldap://your_ldap_server
LDAP_BASEDN=your_base_dn
LDAP_BIND_USER=your_bind_user_dn
LDAP_BIND_PASS=your_bind_password

# App paths
TEMPLATE_FOLDER=templates
STATIC_FOLDER=static
```

⚠️ **Never commit the `.env` file** — it contains sensitive information.

---

## ▶️ Run the Application

```bash
python app.py
```

By default, the app runs on:

```
http://127.0.0.1:5000
```

---

## 🧠 How the App Works

1. User logs in using **LDAP** or a **local account**
2. User is associated with a **team**
3. User can:

   * Create **meetings** (auto-approved)
   * Request **vacations** (pending approval)
4. Managers/Admins:

   * Approve or reject vacation requests
5. Calendar colors indicate:

   * Approved events
   * Pending vacations
   * Rejected vacations

---

## 🎨 Calendar Color Logic

* 🟢 Approved meeting / vacation
* 🟡 Pending vacation
* 🔴 Rejected vacation

*(Exact colors may vary depending on configuration)*

---

## 🔒 Security Notes

* Change the Flask secret key before deployment
* Do not expose the app publicly without authentication hardening
* LDAP credentials should be read-only where possible
* For production use, consider:

  * Gunicorn
  * Reverse proxy (Nginx / Apache)