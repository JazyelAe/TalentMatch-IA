"""Configuración de Django para TalentMatch IA.

Todos los valores sensibles o que cambian entre entornos se leen de variables de entorno
(archivo .env en local). Ver .env.example para la lista completa.
"""

from pathlib import Path

from dotenv import load_dotenv

from config.entorno import leer_bool, leer_float, leer_int, leer_texto, obtener_secret_key

BASE_DIR = Path(__file__).resolve().parent.parent

# Carga .env si existe. Las variables que ya estén en el entorno tienen prioridad.
load_dotenv(BASE_DIR / ".env")

# --- Seguridad ---
DEBUG = leer_bool("DJANGO_DEBUG", por_defecto=True)
SECRET_KEY = obtener_secret_key(leer_texto("DJANGO_SECRET_KEY"), DEBUG)
ALLOWED_HOSTS = [h for h in leer_texto("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]

# --- Aplicaciones ---
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Apps del proyecto
    "vacantes",
    "analisis",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Base de datos ---
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Idioma y zona horaria ---
LANGUAGE_CODE = "es-mx"
TIME_ZONE = "America/Mexico_City"
USE_I18N = True
USE_TZ = True

# --- Archivos estáticos ---
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Archivos subidos ---
# Solo en memoria: el CV nunca se escribe en disco (SPEC F1). Un archivo mayor a este límite
# no se recibe y la vista responde que pesa demasiado (el límite de la app es 5 MB).
FILE_UPLOAD_HANDLERS = ["django.core.files.uploadhandler.MemoryFileUploadHandler"]
FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024

# --- TalentMatch IA: LLM y agente ---
LLM_PROVEEDOR = leer_texto("LLM_PROVEEDOR", "anthropic").lower()
LLM_MODELO = leer_texto("LLM_MODELO", "claude-haiku-5-5")
ANTHROPIC_API_KEY = leer_texto("ANTHROPIC_API_KEY")
AGENTE_MAX_ITERACIONES = leer_int("AGENTE_MAX_ITERACIONES", 8)
MATCH_PESO_DETERMINISTA = leer_float("MATCH_PESO_DETERMINISTA", 0.6)
