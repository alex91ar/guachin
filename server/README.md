# 🛍️ SimpleShop — Flask + DynamoDB Webshop

> A lightweight Python-based webshop with admin and authentication interfaces,  
> built using **Flask**, **Jinja2**, **JWTs**, and **AWS DynamoDB**.

---

## 🚀 Features

- 🧩 **Modular architecture** — blueprints for `/api/v1/auth` and `/api/v1/anon`
- 🔐 **JWT authentication** with optional **Two-Factor Auth (2FA)**
- 🧑‍💼 **Admin interface** under `/admin`
- 🗄️ **AWS DynamoDB** for production, **local DynamoDB** for development
- 🧠 **BaseModel** abstraction for all models (User, Role, Action)
- ⚙️ **Environment-aware config** (development vs production)
- 🧰 **Automatic database seeding** for an admin user
- 🧑‍💻 **Deployment script** for easy setup

---

## 🏗️ Project Structure

