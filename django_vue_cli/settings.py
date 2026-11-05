from pathlib import Path
import sys
import os
import datetime
from django.core.exceptions import ImproperlyConfigured

# lib文件夹中手动导入的第三方库
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(1, os.path.join(os.getcwd(), 'lib'))

try:
    from local_settings import *  # noqa
except ImportError:
    pass

def _load_or_generate_secret_key():
    key = os.getenv("DJANGO_SECRET_KEY", globals().get("SECRET_KEY"))
    if key:
        return key

    # 优先从持久化数据目录 (/app/data/secret.key) 读取或自动生成并持久化，保障 NAS 容器即开即用且重启保持一致
    data_dir = os.path.join(BASE_DIR, "data")
    key_file = os.path.join(data_dir, "secret.key")
    if os.path.exists(key_file):
        try:
            with open(key_file, "r", encoding="utf-8") as f:
                saved = f.read().strip()
                if saved:
                    return saved
        except Exception:
            pass

    import secrets
    new_key = secrets.token_hex(32)
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(key_file, "w", encoding="utf-8") as f:
            f.write(new_key)
    except Exception:
        pass
    return new_key

SECRET_KEY = _load_or_generate_secret_key()

DEBUG = False

ALLOWED_HOSTS = ["*"]
CORS_ALLOW_CREDENTIALS = True
CSRF_COOKIE_NAME = "django_vue_cli_csrftoken"
CORS_ORIGIN_WHITELIST = [
    "http://127.0.0.1:8080"
]

INSTALLED_APPS = [
    "corsheaders",
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    "rest_framework",
    "applications.task",
    "applications.user",
    # "django_extensions",

]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    "component.drf.middleware.AppExceptionMiddleware",
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'django_vue_cli.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, "static", "dist")],
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

WSGI_APPLICATION = 'django_vue_cli.wsgi.application'
TIME_ZONE = "Asia/Shanghai"
LANGUAGE_CODE = "zh-hans"
if os.getenv("dockerrun", "no") == "yes":
    REDIS_HOST = "redis"
    MYSQL_HOST = "db"
else:
    REDIS_HOST = "127.0.0.1"
    MYSQL_HOST = "127.0.0.1"

# Database
DB_DIR = BASE_DIR
if os.path.isdir('/app/data') and os.access('/app/data', os.W_OK):
    DB_DIR = '/app/data'
    root_db = os.path.join(BASE_DIR, 'db.sqlite3')
    data_db = os.path.join(DB_DIR, 'db.sqlite3')
    if os.path.exists(root_db) and not os.path.exists(data_db) and os.path.getsize(root_db) > 0:
        import shutil
        try:
            shutil.copy2(root_db, data_db)
        except Exception:
            pass

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(DB_DIR, 'db.sqlite3'),
        'OPTIONS': {
            'timeout': 20,
        }
    }
}
WORKER_NUM = int(os.getenv("WORKER_NUM", 8))
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.mysql",
#         "NAME": 'music3',  # noqa
#         "USER": "root",
#         "PASSWORD": "123456",
#         "HOST": MYSQL_HOST,
#         "PORT": "3306",
#     },
# }
# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

USE_I18N = True

USE_L10N = True

USE_TZ = False

STATIC_URL = '/static/'
STATIC_ROOT = 'static'
# STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]  # noqa

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "component.drf.generics.exception_handler",
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "component.drf.pagination.CustomPageNumberPagination",
    "PAGE_SIZE": 10,
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_jwt.authentication.JSONWebTokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ),
    "DATETIME_FORMAT": "%Y-%m-%d %H:%M:%S",
    "NON_FIELD_ERRORS_KEY": "params_error",
}

JWT_AUTH = {
    # 过期时间，生成的took七天之后不能使用
    'JWT_EXPIRATION_DELTA': datetime.timedelta(days=7),
    # 刷新时间 之后的token时间值
    'JWT_ALLOW_REFRESH': True,
    'JWT_REFRESH_EXPIRATION_DELTA': datetime.timedelta(days=7),
    # 请求头携带的参数
    'JWT_AUTH_HEADER_PREFIX': 'JWT'
}
BASE_URL = "https://music.163.com/"
REVERSE_PROXY_TYPE = "nginx"
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, "media")
SITE_LOGIN = os.getenv("SITE_LOGIN", "true")
