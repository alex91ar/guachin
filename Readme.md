# 🚀 Guachin — Agent Execution & Control Framework

A modular backend system for managing **agents**, executing **native syscalls**, and dynamically loading **Python-based modules**.

Built with **Flask**, **SQLAlchemy**, and a custom **agent communication layer**.

---

## ✨ Features

- 🧠 **Dynamic module system**
  - Execute Python modules stored in the database
  - Dependency resolution between modules
  - Runtime execution with isolated namespaces

- 🤖 **Agent communication (WebSocket)**
  - Real-time interaction with remote agents
  - Binary protocol for syscall execution
  - Scratchpad-based memory exchange

- 🧬 **Syscall abstraction layer**
  - Native Windows syscalls (Nt*)
  - Structured parameter building
  - Remote execution via injected shellcode

- 🔐 **Authentication system**
  - JWT-based auth
  - Optional 2FA (TOTP)
  - Role-based access control (RBAC)

- 🧑‍💼 **Admin interface**
  - Manage users, roles, actions
  - Manage modules and dependencies
  - Inspect agents

- ⚙️ **Auto bootstrap**
  - Routes → actions mapping
  - Admin user seeding
  - Module auto-loading

---

## 🏗️ Project Structure
```
server/
├── app.py                # Flask app factory
├── deploy.py             # Dev/prod bootstrap script
├── models/               # SQLAlchemy models
├── routes/               # API routes
├── services/             # Core logic (agents, syscalls, execution)
├── modules/              # Dynamic module definitions
├── static/               # Frontend assets
├── templates/            # Jinja templates
└── utils.py              # Helpers
```
---

## ⚡ Quick Start (Dev)

### 1. Run the deploy script

```bash
python deploy.py dev
```
This will:
	* Create virtualenv
	* Install dependencies
	* Start MySQL (Docker)
	* Run migrations / init DB
	* Bootstrap actions + modules
	* Start Gunicorn
	* Start nginx (TLS)

### 2. 🔌 Agent Connection

Agents connect via WebSocket:

/api/v1/anon/agent/ws/<agent_id>

Flow:
	1.	Agent connects
	2.	Handshake initializes:
	* OS
	* Scratchpad memory
	* Syscall table
	3.	Server sends requests
	4.	Agent executes and returns responses


### 3. 🧠 Module System

Modules are stored in DB and executed dynamically.

Example

def function(agent_id, args):
    return {"result": "ok"}

Features
	* Dependency injection
	* Type casting (int, hex, bytes, etc.)
	* Execution sandbox (namespace-based)


### 4. 🔧 Syscall Execution

Supports native Windows syscalls like:
	* NtOpenFile
	* NtCreateSection
	* NtCreateProcessEx
	* NtReadVirtualMemory
	* NtCreateThreadEx

Execution flow:
	1.	Build structures in scratchpad
	2.	Generate shellcode
	3.	Send to agent
	4.	Read result back


### 5. 🗄️ Database

Uses SQLAlchemy + MySQL

Core models:
	* User
	* Role
	* Action
	* Agent
	* Syscall
	* Module


### 6. 🔐 Authentication

JWT (access + refresh)
2FA (TOTP via QR)
Role-based permissions


### 7. Development Tips

Reset DB

CLEAN_DB_ON_EXIT=1 python deploy.py dev

Kill stuck Gunicorn

pkill -f gunicorn

Clean Python cache

find . -type d -name "__pycache__" -exec rm -r {} +


### 8. Notes
	* Configs and modules are loaded at startup → restart required after changes
	* Lazy loading is disabled (lazy='raise_on_sql') → always preload relationships
	* Agent communication is stateful → handle sessions carefully


### 9. Future Improvements
	* Better module sandboxing
	* Async agent handling
	* UI improvements
	* Module hot-reload

### 10. Author

Alejo Popovici (Alex). Senior Cybersecurity Engineer with extensive experience in web application penetration testing, red teaming, source code review, and cloud secu‑
rity (AWS). Skilled in developing custom tooling across multiple languages, with a strong record of identifying logic flaws and privilege escalation
paths.

### 11. Support

btc: bc1qen4gg5rckqk963zrfllg6w6h6aup060g0umh9g
eth/usdt: 0x0866080557dfBbc0c5557d2bB57fe4102038Bd81
monero: 88tRwC8cFEVR7bkRbdmoB1FuVCuabMdGYBGy3BoXKuiuWWcwWW9aiupNa6zT5FCJtqFbGy4q3h4okJbsMn6g7grt4tcEb4t
Ko-fi: [https://ko-fi.com/alex91ar](https://ko-fi.com/alex91ar)

---
