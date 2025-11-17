import os, textwrap

BASE = "full_scheduler_project"

files = {
    # Django project
    f"{BASE}/manage.py": textwrap.dedent("""\
        #!/usr/bin/env python
        import os, sys
        if __name__ == "__main__":
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scheduler.settings")
            from django.core.management import execute_from_command_line
            execute_from_command_line(sys.argv)
    """),

    f"{BASE}/scheduler/__init__.py": "",
    f"{BASE}/scheduler/asgi.py": textwrap.dedent("""\
        import os
        from django.core.asgi import get_asgi_application
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scheduler.settings')
        application = get_asgi_application()
    """),
    f"{BASE}/scheduler/settings.py": textwrap.dedent("""\
        from pathlib import Path
        BASE_DIR = Path(__file__).resolve().parent.parent
        SECRET_KEY = 'dev-key'
        DEBUG = True
        ALLOWED_HOSTS = []
        INSTALLED_APPS = [
            'django.contrib.admin',
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'django.contrib.sessions',
            'django.contrib.messages',
            'django.contrib.staticfiles',
            'booking',
        ]
        MIDDLEWARE = [
            'django.middleware.security.SecurityMiddleware',
            'django.contrib.sessions.middleware.SessionMiddleware',
            'django.middleware.common.CommonMiddleware',
            'django.middleware.csrf.CsrfViewMiddleware',
            'django.contrib.auth.middleware.AuthenticationMiddleware',
            'django.contrib.messages.middleware.MessageMiddleware',
            'django.middleware.clickjacking.XFrameOptionsMiddleware',
        ]
        ROOT_URLCONF = 'scheduler.urls'
        TEMPLATES = [
            {
                'BACKEND': 'django.template.backends.django.DjangoTemplates',
                'DIRS': [BASE_DIR / 'booking' / 'templates'],
                'APP_DIRS': True,
                'OPTIONS': {
                    'context_processors': [
                        'django.template.context_processors.debug',
                        'django.template.context_processors.request',
                        'django.contrib.auth.context_processors.auth',
                        'django.contrib.messages.context_processors.messages',
                    ],
                },
            },
        ]
        WSGI_APPLICATION = 'scheduler.wsgi.application'
        DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}
        AUTH_PASSWORD_VALIDATORS = []
        LANGUAGE_CODE = 'en-us'
        TIME_ZONE = 'UTC'
        USE_I18N = True
        USE_TZ = True
        STATIC_URL = '/static/'
        STATICFILES_DIRS = [BASE_DIR / 'booking' / 'static']
    """),
    f"{BASE}/scheduler/urls.py": textwrap.dedent("""\
        from django.contrib import admin
        from django.urls import path, include
        urlpatterns = [
            path('admin/', admin.site.urls),
            path('', include('booking.urls')),
        ]
    """),
    f"{BASE}/scheduler/wsgi.py": textwrap.dedent("""\
        import os
        from django.core.wsgi import get_wsgi_application
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scheduler.settings')
        application = get_wsgi_application()
    """),

    # Booking app
    f"{BASE}/booking/__init__.py": "",
    f"{BASE}/booking/admin.py": textwrap.dedent("""\
        from django.contrib import admin
        from .models import Slot, Booking
        admin.site.register(Slot)
        admin.site.register(Booking)
    """),
    f"{BASE}/booking/models.py": textwrap.dedent("""\
        from django.db import models
        class Slot(models.Model):
            date = models.DateField()
            time = models.CharField(max_length=20)
            available = models.BooleanField(default=True)
            def __str__(self):
                return f"{self.date} {self.time}"
        class Booking(models.Model):
            name = models.CharField(max_length=100)
            email = models.EmailField()
            slot = models.ForeignKey(Slot, on_delete=models.CASCADE)
            def __str__(self):
                return f"{self.name} - {self.slot}"
    """),
    f"{BASE}/booking/views.py": textwrap.dedent("""\
        import calendar
        from datetime import date
        from django.shortcuts import render, redirect, get_object_or_404
        from .models import Slot, Booking

        OWNER_PASSWORD = "admin123"

        def index(request):
            today = date.today()
            year, month = today.year, today.month
            cal = calendar.Calendar()
            month_days = list(cal.itermonthdates(year, month))
            slots = Slot.objects.filter(date__month=month)
            slot_map = {(s.date, s.time): s.available for s in slots}
            return render(request, "calendar.html", {"days": month_days, "slot_map": slot_map, "month": month, "year": year})

        def admin_login(request):
            if request.method == "POST":
                if request.POST.get("password") == OWNER_PASSWORD:
                    request.session["is_owner"] = True
                    return redirect("/admin_panel/")
            return render(request, "login.html")

        def admin_panel(request):
            if not request.session.get("is_owner"):
                return redirect("/login/")
            if request.method == "POST":
                Slot.objects.create(date=request.POST["date"], time=request.POST["time"], available=True)
            all_slots = Slot.objects.order_by("date")
            return render(request, "admin_panel.html", {"slots": all_slots})

        def book_slot(request, slot_id):
            slot = get_object_or_404(Slot, id=slot_id, available=True)
            if request.method == "POST":
                Booking.objects.create(
                    name=request.POST["name"], email=request.POST["email"], slot=slot)
                slot.available = False
                slot.save()
                return redirect("/")
            return render(request, "book.html", {"slot": slot})
    """),
    f"{BASE}/booking/urls.py": textwrap.dedent("""\
        from django.urls import path
        from . import views
        urlpatterns = [
            path('', views.index),
            path('login/', views.admin_login),
            path('admin_panel/', views.admin_panel),
            path('book/<int:slot_id>/', views.book_slot),
        ]
    """),

    # Templates
    f"{BASE}/booking/templates/base.html": textwrap.dedent("""\
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Scheduler</title>
            <link rel="stylesheet" href="/static/main.css">
            <script src="/static/main.js" defer></script>
        </head>
        <body>
            <header><h1>Scheduler</h1></header>
            <main>{% block content %}{% endblock %}</main>
        </body>
        </html>
    """),
    f"{BASE}/booking/templates/calendar.html": textwrap.dedent("""\
        {% extends 'base.html' %}
        {% block content %}
        <h2>{{ month }}/{{ year }}</h2>
        <div class="calendar">
        {% for day in days %}
            {% if day.month == month %}
            <div class="day">
                <strong>{{ day.day }}</strong><br>
                {% for time in '9am 10am 11am 12pm 1pm 2pm 3pm 4pm'.split %}
                    {% if slot_map|get_item:(day,time) %}
                        <button disabled>{{ time }}</button><br>
                    {% else %}
                        {% if slot_map|get_item:(day,time) is not None %}
                        <a href="/book/{{ slot_map|get_item:(day,time)|yesno:'1,0' }}/">{{ time }}</a><br>
                        {% endif %}
                    {% endif %}
                {% endfor %}
            </div>
            {% else %}
            <div class="empty"></div>
            {% endif %}
        {% endfor %}
        </div>
        {% endblock %}
    """),
    f"{BASE}/booking/templates/login.html": textwrap.dedent("""\
        {% extends 'base.html' %}
        {% block content %}
        <form method="post">{% csrf_token %}
            <input type="password" name="password" placeholder="Owner Password">
            <button type="submit">Login</button>
        </form>
        {% endblock %}
    """),
    f"{BASE}/booking/templates/admin_panel.html": textwrap.dedent("""\
        {% extends 'base.html' %}
        {% block content %}
        <h3>Add Slot</h3>
        <form method="post">{% csrf_token %}
            <input type="date" name="date" required>
            <input type="text" name="time" placeholder="9am" required>
            <button type="submit">Add</button>
        </form>
        <h3>All Slots</h3>
        <ul>
        {% for s in slots %}
            <li>{{ s.date }} - {{ s.time }} {% if not s.available %}(Booked){% endif %}</li>
        {% endfor %}
        </ul>
        {% endblock %}
    """),
    f"{BASE}/booking/templates/book.html": textwrap.dedent("""\
        {% extends 'base.html' %}
        {% block content %}
        <h3>Book {{ slot.date }} at {{ slot.time }}</h3>
        <form method="post">{% csrf_token %}
            <input type="text" name="name" placeholder="Your Name" required>
            <input type="email" name="email" placeholder="Email" required>
            <button type="submit">Confirm</button>
        </form>
        {% endblock %}
    """),

    # Static
    f"{BASE}/booking/static/main.css": textwrap.dedent("""\
        body { font-family:sans-serif; text-align:center; background:#f0f0f0; }
        header { background:#48a; color:white; padding:1em; }
        .calendar { display:grid; grid-template-columns: repeat(7, 1fr); gap:5px; max-width:900px; margin:0 auto; }
        .day { background:white; padding:10px; border-radius:6px; box-shadow:0 0 5px #ccc; }
        .empty { background:transparent; }
        a, button { display:block; margin:2px 0; }
        button:disabled { background:#ccc; }
    """),
    f"{BASE}/booking/static/main.js": textwrap.dedent("""\
        console.log('Scheduler JS loaded');
        // Add future interactivity here (modals, tooltips, etc.)
    """),
}

def create_project():
    for path, content in files.items():
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    print(f"✅ Full scheduler project created at: {os.path.abspath(BASE)}")
    print("Next steps:")
    print("  cd full_scheduler_project")
    print("  pip install django")
    print("  python manage.py migrate")
    print("  python manage.py createsuperuser")
    print("  python manage.py runserver")

if __name__ == "__main__":
    create_project()
