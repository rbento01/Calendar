# Calendar
# 📅 Calendar App – Docker Installation Guide (Ubuntu)

This guide explains how to **quickly install and run the Calendar Flask application on Ubuntu using Docker**.

The setup is designed so you can clone the repository, create a `.env` file, and have the app running in minutes.

---

## 🚀 Requirements

Make sure your Ubuntu system has:

* Ubuntu 20.04+ (22.04 / 24.04 recommended)
* Git
* Docker
* Docker Compose (plugin)

### Install Docker & Docker Compose (if needed)

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable docker --now
```

(Optional but recommended)

```bash
sudo usermod -aG docker $USER
newgrp docker
```

---

## 📥 Clone the Repository

```bash
cd ~
git clone https://github.com/rbento01/Calendar.git
cd Calendar
git checkout Calendar-Ubuntu
```

---

## 🔐 Create the `.env` file

This project **requires a `.env` file** for configuration (Flask, database, LDAP, paths).

Create it in the project root:

```bash
nano .env
```

Paste the following **template** and replace the values with your own:

```env
# Flask / SQLAlchemy
FLASK_SECRET_KEY=your_secret_key_here
SQLALCHEMY_DATABASE_URI=sqlite:////app/instance/calendar.db
SQLALCHEMY_TRACK_MODIFICATIONS=False

# LDAP
LDAP_SERVER=ldap://your_ldap_server
LDAP_BASEDN=your_base_dn
LDAP_BIND_USER=your_bind_user_dn
LDAP_BIND_PASS=your_bind_password

# Paths (Linux container paths)
TEMPLATE_FOLDER=templates
STATIC_FOLDER=static
```

💡 **Important**: Never commit `.env` to GitHub. It contains secrets.

---

## 📂 Create persistent database folder

The application uses SQLite. Create the instance folder:

```bash
mkdir -p instance
```

This folder is mounted into the container so data persists across restarts.

---

## ▶️ Start the Application

### Option A – Using the install script

```bash
chmod +x install.sh
./install.sh
```

### Option B – Manually with Docker Compose

```bash
docker compose down
docker compose build
docker compose up -d
```

---

## 🌐 Access the Application

Find your server IP:

```bash
ip a
```

Then open in a browser:

```
http://<server-ip>:5000
```

Example:

```
http://172.16.30.129:5000
```

---

## 🔍 Useful Commands

View running containers:

```bash
docker ps
```

View logs:

```bash
docker compose logs -f
```

Stop the app:

```bash
docker compose down
```

Restart after updates:

```bash
git pull
docker compose down
docker compose build
docker compose up -d
```

---

## 🧠 How it Works (Quick Overview)

* Docker builds the image using the `Dockerfile`
* The app runs inside a Python 3.11 container
* SQLite database is stored in `./instance/calendar.db`
* LDAP authentication works via environment variables
* Port `5000` is exposed to the host

---

## 🔒 Security Notes

* Do **not** commit `.env`
* Change the Flask secret key
* Use a firewall if exposing this app externally
* For production, consider Gunicorn + Nginx

---

## ✅ Troubleshooting

### App not reachable?

Check container status:

```bash
docker ps -a
```

Check logs:

```bash
docker compose logs
```

### Permission denied to Docker?

```bash
sudo usermod -aG docker $USER
newgrp docker
```

---

### Sync app code from main

To update only the app code from the `main` branch into your current branch:

```bash
git checkout Calendar-Ubuntu
git fetch origin
git checkout origin/main -- app.py templates static
git commit -m "Sync app code from main"
```

**If you want to push the updated code to GitHub, run:**
```bash
git push origin Calendar-Ubuntu
```

---

## 🎉 Done!

Your Calendar application should now be running in Docker on Ubuntu.

If you need help with production hardening, LDAP debugging, or reverse proxy setup, feel free to open an issue.
