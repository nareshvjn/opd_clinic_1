# OPD Clinic 1 & ERPNext Containerized Deployment Guide

This comprehensive guide details the step-by-step setup, configuration, and deployment of **ERPNext** bundled with **Marley (Healthcare)** and the custom **`opd_clinic_1`** application. This setup is optimized for multi-architecture environments, specifically tested on **Oracle Cloud Infrastructure (OCI) Ampere A1 (ARM64 / `linux/arm64`)** as well as standard **x86_64** servers.

---

## Table of Contents
1. [Architecture Overview](#1-architecture-overview)
2. [Prerequisites & Server Preparation](#2-prerequisites--server-preparation)
3. [Project Directory & File Structure](#3-project-directory--file-structure)
4. [Dockerfile Configuration](#4-dockerfile-configuration)
5. [Docker Compose Configuration](#5-docker-compose-configuration)
6. [Step-by-Step Deployment](#6-step-by-step-deployment)
7. [Post-Deployment Verification](#7-post-deployment-verification)
8. [Initial Clinic Configuration (Post-Setup Wizard)](#8-initial-clinic-configuration-post-setup-wizard)
9. [Troubleshooting & Key Fixes](#9-troubleshooting--key-fixes)

---

## 1. Architecture Overview

The stack consists of containerized microservices managed via Docker Compose:
- **`backend`**: Gunicorn WSGI server handling Frappe / ERPNext requests.
- **`frontend`**: Nginx web server routing traffic, serving static assets, and terminating proxy headers.
- **`configurator`**: One-off helper container configuring global bench parameters (`common_site_config.json`).
- **`create-site`**: One-off automation container waiting for DB readiness, creating the site (`frontend`), configuring developer mode & server scripts, installing apps, and migrating schema.
- **`websocket`**: NodeJS Socket.IO service for real-time events.
- **`queue-short` & `queue-long`**: Python background workers processing asynchronous tasks.
- **`scheduler`**: Frappe cron scheduler service.
- **`db`**: MariaDB 11.8 database container.
- **`redis-cache` & `redis-queue`**: Redis 6.2 in-memory stores for caching and queue management.

---

## 2. Prerequisites & Server Preparation

### 2.1 Hardware Requirements
- **Recommended**: Oracle Cloud Free Tier Ampere A1 instance (4 OCPUs, 24 GB RAM, Ubuntu 22.04 or 24.04 AArch64).
- **Disk Space**: At least 50 GB available storage. (On OCI, expand boot volume up to 200 GB for free).

### 2.2 System Setup & Package Installation
```bash
# 1. Update system packages
sudo apt update && sudo apt upgrade -y

# 2. Resize filesystem if running on expanded OCI boot volume
sudo /usr/libexec/oci-growfs || sudo growpart /dev/sda 1 && sudo resize2fs /dev/sda1

# 3. Install Docker and Docker Compose Plugin
sudo apt install -y docker.io docker-compose-plugin git curl jq

# 4. Add current user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

### 2.3 Firewall & Ingress Rules
Ensure ports `80`, `443`, and `8080` (or your reverse proxy port) are allowed:
```bash
# Allow on host firewall
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8080 -j ACCEPT
sudo netfilter-persistent save 2>/dev/null || true
```
*Note: In Oracle Cloud Console, also ensure the Virtual Cloud Network (VCN) Ingress Security Rules permit TCP port 8080 (or 80/443).*

---

## 3. Project Directory & File Structure

Ensure your repository contains the following core files:

```text
opd_clinic_1/
├── Dockerfile                  # Container build recipe
├── compose.yaml                # Stack orchestrator
├── .dockerignore               # Build context exclusions
├── pyproject.toml              # App metadata
├── hooks.py                    # Frappe integration hooks
├── modules.txt                 # Module registry
├── opd_clinic_1/
│   ├── __init__.py             # App package root
│   └── opd_clinic_1/           # Critical: module package matching modules.txt
│       └── __init__.py
├── fixtures/                   # Server scripts, web pages, custom fields
├── scripts/                    # Python API scripts
└── www/                        # Frontend HTML / Jinja pages
```

> **CRITICAL**: Frappe requires the Python subpackage `opd_clinic_1/opd_clinic_1/__init__.py` to match the entry in `modules.txt`. Without it, the setup wizard will fail with `ModuleNotFoundError: No module named 'opd_clinic_1.opd_clinic_1'`.

---

## 4. Dockerfile Configuration

Save the following content as `Dockerfile`:

```dockerfile
# syntax=docker/dockerfile:1

# Supports multi-architecture builds (linux/arm64 for Oracle Ampere & linux/amd64)
ARG ERPNEXT_VERSION=v16.60.0
FROM frappe/erpnext:${ERPNEXT_VERSION}

# Arguments for dependency apps and custom repo
ARG HEALTH_REPO=https://github.com/earthians/marley
ARG HEALTH_BRANCH=develop
ARG OPD_REPO=https://github.com/nareshvjn/opd_clinic_1
ARG OPD_BRANCH=main

USER root
# Install procps (provides `ps` command required by Frappe after_migrate flow-server hook)
RUN apt-get update && apt-get install -y --no-install-recommends procps && rm -rf /var/lib/apt/lists/*

USER frappe
WORKDIR /home/frappe/frappe-bench

# Install Healthcare app dependency (earthians/marley) without compiling frontend assets during image build
RUN bench get-app --branch ${HEALTH_BRANCH} --skip-assets ${HEALTH_REPO}

# Get and install opd_clinic_1 directly from GitHub
RUN bench get-app --branch ${OPD_BRANCH} --skip-assets ${OPD_REPO}
```

---

## 5. Docker Compose Configuration

Save the following configuration as `compose.yaml`:

```yaml
services:
  backend:
    build: .
    image: frappe/erpnext:v16.60.0
    networks:
      - frappe_network
    deploy:
      restart_policy:
        condition: on-failure
    volumes:
      - sites:/home/frappe/frappe-bench/sites
      - logs:/home/frappe/frappe-bench/logs
    environment:
      DB_HOST: db
      DB_PORT: "3306"
      MYSQL_ROOT_PASSWORD: admin
      MARIADB_ROOT_PASSWORD: admin
    depends_on:
      configurator:
        condition: service_completed_successfully
      create-site:
        condition: service_completed_successfully

  configurator:
    build: .
    image: frappe/erpnext:v16.60.0
    restart: "no"
    networks:
      - frappe_network
    deploy:
      restart_policy:
        condition: none
    entrypoint:
      - bash
      - -c
    command:
      - >
        ls -1 apps > sites/apps.txt;
        bench set-config -g db_host $$DB_HOST;
        bench set-config -gp db_port $$DB_PORT;
        bench set-config -g redis_cache "redis://$$REDIS_CACHE";
        bench set-config -g redis_queue "redis://$$REDIS_QUEUE";
        bench set-config -g redis_socketio "redis://$$REDIS_QUEUE";
        bench set-config -gp socketio_port $$SOCKETIO_PORT;
        bench set-config -g developer_mode 1;
        bench set-config -g server_script_enabled true;
    environment:
      DB_HOST: db
      DB_PORT: "3306"
      REDIS_CACHE: redis-cache:6379
      REDIS_QUEUE: redis-queue:6379
      SOCKETIO_PORT: "9000"
    volumes:
      - sites:/home/frappe/frappe-bench/sites
      - logs:/home/frappe/frappe-bench/logs

  create-site:
    build: .
    image: frappe/erpnext:v16.60.0
    restart: "no"
    networks:
      - frappe_network
    deploy:
      restart_policy:
        condition: none
    volumes:
      - sites:/home/frappe/frappe-bench/sites
      - logs:/home/frappe/frappe-bench/logs
    entrypoint:
      - bash
      - -c
    command:
      - >
        wait-for-it -t 120 db:3306;
        wait-for-it -t 120 redis-cache:6379;
        wait-for-it -t 120 redis-queue:6379;
        export start=`date +%s`;
        until [[ -n `grep -hs ^ sites/common_site_config.json | jq -r ".db_host // empty"` ]] && \
          [[ -n `grep -hs ^ sites/common_site_config.json | jq -r ".redis_cache // empty"` ]] && \
          [[ -n `grep -hs ^ sites/common_site_config.json | jq -r ".redis_queue // empty"` ]];
        do
          echo "Waiting for sites/common_site_config.json to be created";
          sleep 5;
          if (( `date +%s`-start > 120 )); then
            echo "could not find sites/common_site_config.json with required keys";
            exit 1
          fi
        done;
        echo "sites/common_site_config.json found";
        SITE="frontend";
        if [ -d "sites/frontend" ]; then
          echo "Site frontend already exists, skipping creation";
        else
          bench new-site --mariadb-user-host-login-scope='%' --admin-password=admin --db-root-username=root --db-root-password=admin --install-app erpnext --set-default frontend;
        fi;
        bench --site "$$SITE" set-config developer_mode 1;
        bench --site "$$SITE" set-config server_script_enabled 1;
        bench --site "$$SITE" install-app healthcare 2>/dev/null || bench --site "$$SITE" install-app marley 2>/dev/null || true;
        bench --site "$$SITE" install-app opd_clinic_1 2>/dev/null || true;
        bench --site "$$SITE" migrate;
        bench --site "$$SITE" clear-cache;
    depends_on:
      configurator:
        condition: service_completed_successfully

  db:
    image: mariadb:11.8
    networks:
      - frappe_network
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
      start_period: 5s
      interval: 5s
      timeout: 5s
      retries: 5
    deploy:
      restart_policy:
        condition: on-failure
    command:
      - --character-set-server=utf8mb4
      - --collation-server=utf8mb4_unicode_ci
      - --skip-character-set-client-handshake
      - --innodb-snapshot-isolation=OFF
    environment:
      MYSQL_ROOT_PASSWORD: admin
      MARIADB_ROOT_PASSWORD: admin
    volumes:
      - db-data:/var/lib/mysql

  frontend:
    build: .
    image: frappe/erpnext:v16.60.0
    networks:
      - frappe_network
      - npm_default
    depends_on:
      - websocket
      - backend
    deploy:
      restart_policy:
        condition: on-failure
    command:
      - nginx-entrypoint.sh
    environment:
      BACKEND: backend:8000
      FRAPPE_SITE_NAME_HEADER: frontend
      SOCKETIO: websocket:9000
      UPSTREAM_REAL_IP_ADDRESS: 127.0.0.1
      UPSTREAM_REAL_IP_HEADER: X-Forwarded-For
      UPSTREAM_REAL_IP_RECURSIVE: "off"
      PROXY_READ_TIMEOUT: 120
      CLIENT_MAX_BODY_SIZE: 50m
    volumes:
      - sites:/home/frappe/frappe-bench/sites
      - logs:/home/frappe/frappe-bench/logs
    ports:
      - "8080:8080"

  queue-long:
    build: .
    image: frappe/erpnext:v16.60.0
    networks:
      - frappe_network
    deploy:
      restart_policy:
        condition: on-failure
    command:
      - bench
      - worker
      - --queue
      - long,default,short
    volumes:
      - sites:/home/frappe/frappe-bench/sites
      - logs:/home/frappe/frappe-bench/logs
    environment:
      FRAPPE_REDIS_CACHE: redis://redis-cache:6379
      FRAPPE_REDIS_QUEUE: redis://redis-queue:6379
    depends_on:
      configurator:
        condition: service_completed_successfully

  queue-short:
    build: .
    image: frappe/erpnext:v16.60.0
    networks:
      - frappe_network
    deploy:
      restart_policy:
        condition: on-failure
    command:
      - bench
      - worker
      - --queue
      - short,default
    volumes:
      - sites:/home/frappe/frappe-bench/sites
      - logs:/home/frappe/frappe-bench/logs
    environment:
      FRAPPE_REDIS_CACHE: redis://redis-cache:6379
      FRAPPE_REDIS_QUEUE: redis://redis-queue:6379
    depends_on:
      configurator:
        condition: service_completed_successfully

  redis-queue:
    image: redis:6.2-alpine
    networks:
      - frappe_network
    deploy:
      restart_policy:
        condition: on-failure
    volumes:
      - redis-queue-data:/data

  redis-cache:
    image: redis:6.2-alpine
    networks:
      - frappe_network
    deploy:
      restart_policy:
        condition: on-failure

  scheduler:
    build: .
    image: frappe/erpnext:v16.60.0
    networks:
      - frappe_network
    deploy:
      restart_policy:
        condition: on-failure
    command:
      - bench
      - schedule
    volumes:
      - sites:/home/frappe/frappe-bench/sites
      - logs:/home/frappe/frappe-bench/logs
    depends_on:
      configurator:
        condition: service_completed_successfully

  websocket:
    build: .
    image: frappe/erpnext:v16.60.0
    networks:
      - frappe_network
    deploy:
      restart_policy:
        condition: on-failure
    command:
      - node
      - /home/frappe/frappe-bench/apps/frappe/socketio.js
    environment:
      FRAPPE_REDIS_CACHE: redis://redis-cache:6379
      FRAPPE_REDIS_QUEUE: redis://redis-queue:6379
    volumes:
      - sites:/home/frappe/frappe-bench/sites
      - logs:/home/frappe/frappe-bench/logs
    depends_on:
      configurator:
        condition: service_completed_successfully

volumes:
  db-data:
  redis-queue-data:
  sites:
  logs:

networks:
  frappe_network:
    driver: bridge
  npm_default:
    external: true
```

---

## 6. Step-by-Step Deployment

### Step 1: Create External Network
The stack attaches to an external network `npm_default` (commonly used for Nginx Proxy Manager). If not already present, create it:
```bash
docker network create npm_default || true
```

### Step 2: Build the Image
Build the container image with no cache to ensure the latest upstream apps are fetched:
```bash
docker compose build --no-cache
```

### Step 3: Start the Stack
Start the containers in detached mode:
```bash
docker compose up -d
```

### Step 4: Monitor Setup Progress
Follow the `create-site` container logs until site initialization completes:
```bash
docker compose logs -f create-site
```
You should see:
1. `sites/common_site_config.json found`
2. `Creating site frontend...`
3. `App healthcare installed`
4. `App opd_clinic_1 installed`
5. `Migrating frontend`
6. `create-site` container cleanly exiting with code `0`.

---

## 7. Post-Deployment Verification

1. **Access Web Interface**:
   - Open `http://<YOUR_SERVER_IP>:8080` in your web browser.
   - If using Nginx Proxy Manager, route your domain (e.g. `clinic.yourdomain.com`) to the `frontend` container on port `8080`.

2. **Complete Frappe Setup Wizard**:
   - Language: English
   - Country & Currency: India (INR) / Your preference
   - Administrator Account: Set your administrative email and password
   - Organization: Provide your clinic or organization details.

3. **Verify Installed Apps**:
   In Frappe Desk, navigate to **Help > About** or run inside the container:
   ```bash
   docker compose exec backend bench --site frontend list-apps
   ```
   You should see:
   - `frappe`
   - `erpnext`
   - `healthcare` (or `marley`)
   - `opd_clinic_1`

---

## 8. Initial Clinic Configuration (Post-Setup Wizard)

Once the Frappe setup wizard has finished, follow these mandatory steps in the Frappe Desk to configure the clinic entities required by `opd_clinic_1` (such as Doctor Desk, Appointment Booking, Patient Vitals, Pharmacy, and Invoicing):

### 8.1 Company & Global Defaults
1. **Verify Default Company**:
   - Navigate to **Global Defaults** using the Awesome Bar (search bar).
   - Ensure **Default Company** is set to your clinic (e.g. `Jeevan Healthcare And Medicals`).
   - Ensure **Default Currency** is set (e.g. `INR`).
2. **Company Accounts & Default Warehouse**:
   - Navigate to **Company > [Your Company]**.
   - Under **Account Settings**, ensure the default accounts are configured:
     - **Default Receivable Account**: `Debtors - [ABBR]`
     - **Default Payable Account**: `Creditors - [ABBR]`
     - **Default Cost Center**: `Main - [ABBR]`
     - **Stock Adjustment Account**: `Stock Adjustment - [ABBR]`
     - **Default Inventory Account**: `Stock In Hand - [ABBR]`
     - **Round Off Account**: `Round Off - [ABBR]`
     - **Default Warehouse**: Set to your pharmacy or main store warehouse (e.g. `Stores - [ABBR]`).
3. **Clinic Address & Contact**:
   - Scroll down to the **Address and Contact** section on the Company page > click **New Address**.
   - Enter your Clinic Address, City, State, Country, Postal Code, and Phone Number.
   - Check **Is Your Company Address** and click **Save**.
   - *Note: This address is dynamically rendered on prescriptions, print formats, and patient bills.*

---

### 8.2 Healthcare Settings
- Navigate to **Healthcare Settings**:
  - **Link Customer to Patient**: Enable this checkbox so billing patients automatically creates and associates a Customer record in ERPNext Accounts.
  - **Income Account**: Ensure default healthcare service income account is linked.
  - **Invoicing Settings**: Enable automatic appointment invoicing or set your clinic's billing preference.

---

### 8.3 Medical Department
- Navigate to **Medical Department > New**:
  - Create the clinical departments operating in your clinic, for example:
    - `General Medicine`
    - `Pediatrics`
    - `Cardiology`
    - `Orthopedics`
    - `Dental`

---

### 8.4 Practitioner Schedule (Working Hours & Slot Duration)
*Required by the appointment engine (`appt_slots.py`) to generate available booking slots on the portal.*
- Navigate to **Practitioner Schedule > New**:
  - **Schedule Name**: e.g., `Morning OPD Schedule` (or `General OPD Shift`).
  - **Slot Duration (Minutes)**: Set your consultation duration, e.g., `15` (or `20` / `30` mins per slot).
  - **Time Slots Table**:
    - Add rows for working days:
      - Day: `Monday`, From Time: `09:00:00`, To Time: `13:00:00`
      - Day: `Tuesday`, From Time: `09:00:00`, To Time: `13:00:00`
      - Day: `Wednesday`, From Time: `09:00:00`, To Time: `13:00:00`
      - Day: `Thursday`, From Time: `09:00:00`, To Time: `13:00:00`
      - Day: `Friday`, From Time: `09:00:00`, To Time: `13:00:00`
      - Day: `Saturday`, From Time: `09:00:00`, To Time: `13:00:00`
  - Optionally create an `Evening OPD Schedule` (e.g., `17:00:00` to `20:00:00`) if your clinic runs split shifts.

---

### 8.5 Healthcare Practitioner (Doctor Profile & Account Linking)
*CRITICAL: Every consulting doctor must have a Healthcare Practitioner record linked to their ERPNext user account.*

1. **Create the Doctor's User Account**:
   - Navigate to **User > New**.
   - Enter doctor email (e.g., `doctor@clinic.com`) and Name.
   - Under **Roles**, check:
     - **Physician**
     - **Healthcare Administrator** (if administrative privileges are required)
     - **Desk User**
   - Save and set password.

2. **Create the Healthcare Practitioner Record**:
   - Navigate to **Healthcare Practitioner > New**:
   - **Practitioner Name**: e.g., `Dr. Naresh Kumar`.
   - **Status**: Set to `Active`.
   - **User ID**: Select the doctor's user account (e.g. `doctor@clinic.com` or `Administrator`).
     > **IMPORTANT**: The script `desk_data.py` looks up practitioners using `filters={"user_id": user}`. If `User ID` is blank, navigating to `/doctor-desk` will throw: *"Your user isn't linked to a Healthcare Practitioner. Ask an administrator to set the User ID on your practitioner record."*
   - **Department**: Link to the relevant Medical Department (e.g., `General Medicine`).
   - **Practitioner Schedule Table**:
     - Click **Add Row** > select the schedule created in Step 8.4 (`Morning OPD Schedule`).
   - **Practitioner Charges Table**:
     - Add Consultation Charge: Service Item: `OPD Consultation`, Fee/Amount: `300.00`.
   - Save the record.

---

### 8.6 User Roles & Custom Portal Access
Assign the appropriate roles to your clinic staff in **User > [User Profile] > Roles**:
- **Doctors / Consultants**: Roles `Physician`, `Desk User`  
  *Access to:* `/doctor-desk`, `/consultation`, `/sale-return`, `/purchase-return`.
- **Nurses / Triage Staff**: Roles `Nursing User`, `Desk User`  
  *Access to:* `/vitals`, `/registration`.
- **Reception / Front Desk**: Roles `Healthcare Administrator` or `Desk User`  
  *Access to:* `/registration`, `/doctors`, appointment booking `/contact`.
- **Pharmacist / Inventory Managers**: Roles `Stock User`, `Stock Manager`, `Desk User`  
  *Access to:* `/pharmacy`, `/pharmacy-home`, `/new-sale`, `/new-purchase`, `/distributor-bills`, `/stock-import`, `/add-stock`.

---

### 8.7 Pharmacy & Warehouse Setup
1. **Warehouse**:
   - Navigate to **Warehouse > New**.
   - Create a warehouse under your company (e.g., `Pharmacy - [ABBR]`).
   - Set as `default_warehouse` in Company settings.
2. **Price Lists**:
   - Verify that **Standard Selling** and **Standard Buying** price lists are enabled with your currency (`INR`).
3. **Batch & GST Tracking**:
   - `opd_clinic_1` comes pre-configured with custom batch fields (`gst_rate`, `hsn_code`, `mrp`, `net_rate`, `purchase_rate`, `units_per_pack`) which automatically track medicine batches, expiry dates, and distributor pricing during purchase and sale workflows.

---

## 9. Troubleshooting & Key Fixes

### 1. `ModuleNotFoundError: No module named 'opd_clinic_1.opd_clinic_1'`
- **Cause**: During the setup wizard, `sync_dashboards()` looks for a module directory matching each item in `modules.txt`. If `opd_clinic_1` is listed in `modules.txt`, Python attempts to import `opd_clinic_1.opd_clinic_1`.
- **Resolution**: Ensure the subpackage folder `opd_clinic_1/opd_clinic_1/__init__.py` exists in your repository.

### 2. `create-site` Container in Restart Loop
- **Cause**: In Docker Compose (without Swarm), `deploy.restart_policy` is ignored. If `restart: "no"` is omitted, Compose restarts one-off setup containers infinitely.
- **Resolution**: Ensure `restart: "no"` is explicitly declared under `create-site` and `configurator`.

### 3. `flow server not running: [Errno 2] No such file or directory: 'ps'`
- **Cause**: Frappe v16 after-migration hooks check for background workers using Linux `ps`. Base images do not include `procps` by default.
- **Resolution**: Added `apt-get install -y procps` under `USER root` in the `Dockerfile`.

### 4. Custom App Installation Requires Developer Mode
- **Cause**: Custom apps containing fixtures and server scripts require `developer_mode` active during installation.
- **Resolution**: Both `configurator` (via `bench set-config -g developer_mode 1`) and `create-site` (via `bench --site frontend set-config developer_mode 1`) set developer mode before installing `opd_clinic_1`.
