
<h1 align="center">⚙️🗄️ Centryx Backend Application</h1>

<h2 align="center">Technologies</h2>

<div align="center">
  <table>
    <tr>
      <th>Language</th>
      <th>Framework</th>
      <th>REST Framework</th>
      <th>Caching</th>
      <th>Database</th>
    </tr>
    <tr>
      <td><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/python/python-original.svg" alt="Python" width="60"/><br/>Python</td>
      <td><img src="https://www.svgrepo.com/show/353657/django-icon.svg" alt="Django" width="60"/><br/>Django</td>
      <td><img src="https://www.django-rest-framework.org/img/logo.png" alt="DRF" width="60"/><br/>Django REST Framework</td>
      <td><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/redis/redis-original.svg" alt="Redis" width="60"/><br/>Redis</td>
      <td><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/postgresql/postgresql-original.svg" alt="PostgreSQL" width="60"/><br/>PostgreSQL</td>
    </tr>
  </table>
</div>

> **Note:** Make sure that the above technologies are installed and working properly before running the application or any background tasks. Run the commands below from the root directory in order (where manage.py is located).


### Install Python Requirements

```bash
cd ~/Final-Year-Project
pip install -r requirements/requirements.txt
```

### Run Celery Worker

```bash
celery -A Centryx worker --loglevel=info
```

### Run Celery Beat (Task Scheduler)

```bash
celery -A Centryx beat --loglevel=info
```

### Run Tests

```bash
python manage.py test
```

### Populate the database

```bash
python manage.py populate
```

### Run the Backend

```bash
python manage.py runserver
```
