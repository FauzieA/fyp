

<h1 align="center">⚙️ Centryx Backend Application</h1>

<p align="center">
<b>A robust backend for Centryx, built with modern technologies for scalable and efficient web applications.</b>
</p>

---

## 🚀 Technologies Used

<div align="center">
  <table>
    <tr>
      <th>Language</th>
      <th>Framework</th>
      <th>REST API</th>
      <th>Caching</th>
      <th>Database</th>
    </tr>
    <tr>
      <td><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/python/python-original.svg" alt="Python" width="40"/><br/>Python</td>
      <td><img src="https://www.svgrepo.com/show/353657/django-icon.svg" alt="Django" width="40"/><br/>Django</td>
      <td><img src="https://www.django-rest-framework.org/img/logo.png" alt="DRF" width="40"/><br/>DRF</td>
      <td><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/redis/redis-original.svg" alt="Redis" width="40"/><br/>Redis</td>
      <td><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/postgresql/postgresql-original.svg" alt="PostgreSQL" width="40"/><br/>PostgreSQL</td>
    </tr>
  </table>
</div>

---


## 📝 Notes

- Make sure your virtual environment is activated before installing requirements.
- Update `requirements/requirements.txt` as needed for new dependencies.
- For production, configure environment variables and security settings appropriately.

## ⚡️ Getting Started

> **Note:** Ensure all technologies above are installed and working. Run the following commands from your project root (where `manage.py` is located):

### 1. Install Python Requirements

```bash
cd ~/Final-Year-Project
pip install -r requirements/requirements.txt
```

### 2. Migrate and Populate the Database

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py populate
```

### 3. Run Tests

```bash
python manage.py test
```

### 4. Start Celery Worker

```bash
celery -A Centryx worker --loglevel=info
```

### 5. Start Celery Beat (Task Scheduler)

```bash
celery -A Centryx beat --loglevel=info
```

### 6. Run the Backend Server

```bash
python manage.py runserver
```

---

## 📂 Project Structure

```
Final-Year-Project/
├── Centryx/           # Django project source
├── requirements/      # Python dependencies and 
├── manage.py          # Django management script
└── ...                # Other files and folders
```

---
