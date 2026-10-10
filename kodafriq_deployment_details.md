# 🚀 Kodafriq Production Deployment & Server Runbook
**Kodafriq Data Management Solutions**  
*Hostinger VPS Production Environment Reference & Standard Operating Procedures (SOP)*

---

## 📌 1. Server & Environment Specification

| Parameter | Production Value / Location | Notes |
| :--- | :--- | :--- |
| **Hosting Provider** | Hostinger VPS (Cloud Server) | Managed via Hostinger Web Terminal / SSH |
| **Server Hostname** | `srv2028220` | User: `root@srv2028220` |
| **Project Root Directory** | `/var/www/kodafriq` | Primary codebase directory |
| **Virtual Environment** | `/var/www/kodafriq/venv` | Python 3.12 environment |
| **Application Systemd Service** | `kodafriq` (`kodafriq.service`) | WSGI / Gunicorn application daemon |
| **Reverse Proxy & Web Server** | Nginx | Serves static/media assets & proxies HTTP |
| **Static Files (Source)** | `/var/www/kodafriq/static` | Project repository assets |
| **Static Files (Collected)** | `/var/www/kodafriq/staticfiles` | Collected bundle served by Nginx |
| **Media & Uploads Directory** | `/var/www/kodafriq/media` | Resumes, certificates, and flyers |
| **Database File** | `/var/www/kodafriq/db.sqlite3` | SQLite production database |
| **Environment Secrets** | `/var/www/kodafriq/.env` | Secret key, production settings, API keys |
| **Repository Remote** | `git@github.com:kinghez/kodafriq.git` | Branch: `main` |

---

## ⚡ 2. One-Liner Quick Update Command

To deploy future updates pushed to `main`, connect to the server and run:

```bash
cd /var/www/kodafriq && git pull origin main && source venv/bin/activate && python manage.py migrate && python manage.py collectstatic --noinput && sudo systemctl restart kodafriq && sudo systemctl reload nginx
```

---

## 🛠️ 3. Step-by-Step Deployment Procedure

### Step 1: Navigate to the Project Root
```bash
cd /var/www/kodafriq
```

### Step 2: Pull the Latest Code from GitHub
```bash
git pull origin main
```

### Step 3: Activate the Virtual Environment
```bash
source venv/bin/activate
```
*(Terminal prompt changes to `(venv)`)*

### Step 4: Run Database Migrations
```bash
python manage.py migrate
```
*Applies all new schema changes and data migrations.*

### Step 5: Collect Static Files
```bash
python manage.py collectstatic --noinput
```
*Gathers CSS, JavaScript, and images into `/var/www/kodafriq/staticfiles`.*

### Step 6: Restart the Application Service
```bash
sudo systemctl restart kodafriq
```
*Restarts the Django Gunicorn worker processes running the site.*

### Step 7: Reload Nginx
```bash
sudo systemctl reload nginx
```
*Flushes web server worker caches without dropping active connections.*

---

## 🔍 4. Verification, Health Checks & Monitoring

### Check Application Service Status
```bash
sudo systemctl status kodafriq
```

### Stream Live Application Logs
```bash
sudo journalctl -u kodafriq -f --lines=50
```

### Check Nginx Configuration & Logs
```bash
# Test Nginx syntax
sudo nginx -t

# Stream live Nginx error logs
sudo tail -f /var/log/nginx/error.log

# Stream live Nginx access logs
sudo tail -f /var/log/nginx/access.log
```

---

## 🛡️ 5. Routine Maintenance & Backup Procedures

### Quick Database Backup
Before applying large database migrations, back up the SQLite database:
```bash
cp /var/www/kodafriq/db.sqlite3 /var/www/kodafriq/db_backup_$(date +%Y%m%d_%H%M%S).sqlite3
```

### Fix File Permissions
Ensure the web server user (`www-data` or `root`) can read/write media and static files:
```bash
chmod -R 755 /var/www/kodafriq/media /var/www/kodafriq/staticfiles
```
