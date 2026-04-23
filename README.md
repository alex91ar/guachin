# 🚀 Guachin — Agent Execution & Control Framework

Main Repo: [https://github.com/alex91ar/guachin](https://github.com/alex91ar/guachin)

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
  - Native Windows syscalls (`Nt*`)  
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

- Create virtualenv  
- Install dependencies  
- Start MySQL (Docker)  
- Run migrations / init DB  
- Bootstrap actions + modules  
- Start Gunicorn  
- Start nginx (TLS)  

---

## 🔌 Agent Connection

Agents connect via WebSocket:

```
/api/v1/anon/agent/ws/<agent_id>
```

### Flow

1. Agent connects  
2. Handshake initializes:
   - OS  
   - Scratchpad memory  
   - Syscall table  
3. Server sends requests  
4. Agent executes and returns responses  

---

## 🧠 Module System

Modules are stored in the DB and executed dynamically.

### Example

```python
def function(agent_id, args):
    return {"result": "ok"}
```

### Features

- Dependency injection  
- Type casting (`int`, `hex`, `bytes`, etc.)  
- Execution sandbox (namespace-based)  

---

## 🔧 Syscall Execution

Supports native Windows syscalls such as:

- `NtOpenFile`  
- `NtCreateSection`  
- `NtCreateProcessEx`  
- `NtReadVirtualMemory`  
- `NtCreateThreadEx`  

### Execution flow

1. Build structures in scratchpad  
2. Generate shellcode  
3. Send to agent  
4. Read result back  

---

## 🗄️ Database

Uses **SQLAlchemy + MySQL**

### Core models

- User  
- Role  
- Action  
- Agent  
- Syscall  
- Module  

---

## 🔐 Authentication

- JWT (access + refresh)  
- 2FA (TOTP via QR)  
- Role-based permissions  

---

## 🛠️ Development Tips

### Reset DB

```bash
CLEAN_DB_ON_EXIT=1 python deploy.py dev
```

### Kill stuck Gunicorn

```bash
pkill -f gunicorn
```

### Clean Python cache

```bash
find . -type d -name "__pycache__" -exec rm -r {} +
```

---

## 📌 Notes

- Configs and modules are loaded at startup → restart required after changes  
- Lazy loading is disabled (`lazy='raise_on_sql'`) → always preload relationships  
- Agent communication is stateful → handle sessions carefully  

---

## 🚧 Future Improvements

- Better module sandboxing  
- Async agent handling  
- UI improvements  
- Module hot-reload  

---

## 👤 Author

**Alejo Popovici (Alex)**  
Senior Cybersecurity Engineer with experience in:

- Web application penetration testing  
- Red teaming  
- Source code review  
- Cloud security (AWS)  

Skilled in developing custom tooling across multiple languages, with a strong track record in identifying logic flaws and privilege escalation paths.

## Legal considerations

This project is intended for legitimate security research and authorized
red teaming activities only.

By using this software, you agree that:
- You will only use it on systems you own or have explicit permission to test
- You will comply with all applicable laws and regulations
- You are solely responsible for your actions and any consequences

Unauthorized use of this software against systems, networks, or devices
without prior consent is illegal and strictly discouraged.

The author does not condone or support malicious use of this software.

If you use, modify, or distribute this project, you must:

- Include the original copyright notice and license
- Provide clear credit to the original author
- Indicate if changes were made

Suggested attribution format:

"Based on guachin by Alejo Popovici (https://github.com/alex91ar/guachin)[https://github.com/alex91ar/guachin]"

---

## 💖 Support

- **BTC**:  
  `bc1qen4gg5rckqk963zrfllg6w6h6aup060g0umh9g`

- **ETH / USDT**:  
  `0x0866080557dfBbc0c5557d2bB57fe4102038Bd81`

- **Monero**:  
  `88tRwC8cFEVR7bkRbdmoB1FuVCuabMdGYBGy3BoXKuiuWWcwWW9aiupNa6zT5FCJtqFbGy4q3h4okJbsMn6g7grt4tcEb4t`

- **Ko-fi**:  
  https://ko-fi.com/alex91ar

---
