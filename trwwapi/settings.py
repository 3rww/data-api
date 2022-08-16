"""
Django settings for trwwapi project.
"""

import os
from os.path import join, dirname
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

# .env file path:
dotenv_path = join(dirname(__file__), '../.env')
# Load .env file:
load_dotenv(dotenv_path)

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
base_dir_path = Path(BASE_DIR)
main_app_name = 'trwwapi'


# Development settings
# See https://docs.djangoproject.com/en/3.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', False)
# print("DEBUG", DEBUG)
# Check for these variables, each defined as a comma-separated string in the .env file

ALLOWED_HOSTS = [path for path in os.environ.get('ALLOWED_HOSTS', '').split(',') if path]
# print("ALLOWED_HOSTS", ALLOWED_HOSTS)

# For CORS (corsheaders app)
CORS_ORIGIN_WHITELIST = [path for path in os.environ.get('CORS_ORIGIN_WHITELIST', '').split(',') if path]
# print("CORS_ORIGIN_WHITELIST", CORS_ORIGIN_WHITELIST)

# For the Django Debug Toolbar (debug_toolbar app):
INTERNAL_IPS = [path for path in os.environ.get('INTERNAL_IPS', '').split(',') if path]
# print("INTERNAL_IPS", INTERNAL_IPS)

# Application definition

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # 3rd party apps
    'debug_toolbar',
    'django_rq',
    'corsheaders',
    'rest_framework',
    'rest_framework_gis',
    'drf_spectacular',
    'django_filters',
    'leaflet',
    'taggit',
    # 'storages',
    # 'cloud_browser',
    # our apps
    'trwwapi.rainfall',
    'trwwapi.rainways'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'trwwapi.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            str(base_dir_path / main_app_name / 'templates')
        ],
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

WSGI_APPLICATION = 'trwwapi.wsgi.application'


# Database
# https://docs.djangoproject.com/en/3.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT')
    },
    'rainfall_db': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.getenv('RAINFALL_DB_NAME'),
        'USER': os.getenv('RAINFALL_DB_USER'),
        'PASSWORD': os.getenv('RAINFALL_DB_PASSWORD'),
        'HOST': os.getenv('RAINFALL_DB_HOST'),
        'PORT': os.getenv('RAINFALL_DB_PORT')
    }    
}

# use the connection string in DATABASE_URL if found in environment
# (utilized by Heroku, can optionally be used locally to override)
if 'DATABASE_URL' in os.environ.keys():
    db_from_env = dj_database_url.config(conn_max_age=600, ssl_require=True) # gets from DATABASE_URL environment variable
    DATABASES['default'].update(db_from_env)
    DATABASES['default']['ENGINE'] = 'django.contrib.gis.db.backends.postgis'

if 'RAINFALL_RDS_DATABASE_URL' in os.environ.keys():
    DATABASES['rainfall_db'] = dj_database_url.parse(os.getenv('RAINFALL_RDS_DATABASE_URL'), conn_max_age=600, ssl_require=True)
    DATABASES['rainfall_db']['ENGINE'] = 'django.contrib.gis.db.backends.postgis'

DATABASE_ROUTERS = (
    'trwwapi.routers.RainfallDbRouter',
    'trwwapi.routers.DefaultRouter'
)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# caching
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        # 'TIMEOUT': 15,
        'OPTIONS': {
            'MAX_ENTRIES': 10
        }
    }
}


# Password validation
# https://docs.djangoproject.com/en/3.0/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/3.0/topics/i18n/

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/New_York'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# ------------------------------------------------------------------------------
# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.0/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

# NOTE: this is disabled due to this issue: https://github.com/encode/django-rest-framework/issues/8608
# with Django 4.1, Whitenoise, and DRF
# STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder'
]

STATICFILES_DIRS = [
    str(base_dir_path / main_app_name / 'static')
]

# ------------------------------------------------------------------------------
# GDAL & GEOS

GDAL_LIBRARY_PATH = os.environ.get('GDAL_LIBRARY_PATH')
GEOS_LIBRARY_PATH = os.environ.get('GEOS_LIBRARY_PATH')

# ------------------------------------------------------------------------------
# REST FRAMEWORK + API DOCS SETTINGS

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    # 'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    # 'PAGE_SIZE': 20,
    'DEFAULT_METADATA_CLASS': 'rest_framework.metadata.SimpleMetadata',
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend'
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema'
}

SPECTACULAR_SETTINGS = {
    'TITLE': '3RWW Rainfall API',
    'DESCRIPTION': 'Get 3RWW high-resolution rainfall data',
    'CONTACT': {"name": "CivicMapper", "email": "3rww@civicmapper.com"},
    # Optional: MUST contain "name", MAY contain URL
    'LICENSE': {"name":"MIT"},
    'VERSION': '2.0.0'
}


# ------------------------------------------------------------------------------
# JOB QUEUES
# Using Python RQ via Django RQ here. Note that the URL for Redis will come
# from the env by default--this is the case in production. For development, it's
# looking for the named container 'redis' as stood up by docker-compose

RQ_QUEUES = {
    'default': {
        'URL': os.getenv('REDIS_URL', 'redis://redis:6379/0'),
        'DEFAULT_TIMEOUT': 900,
    }
}

# RQ_API_TOKEN=os.getenv('RQ_API_TOKEN', 'test-rq-token')
RQ_SHOW_ADMIN_LINK = True

# ------------------------------------------------------------------------------
# Object Storage
# Access to static files stored on AWS S3 by 3rww-rainfall-pipeline and others

# django-storages
'''
DEFAULT_FILE_STORAGE = 'storages.backends.apache_libcloud.LibCloudStorage'

LIBCLOUD_PROVIDERS = {
    'trww_rainfall_reports': {
        'type': 'libcloud.storage.types.Provider.S3_US_STANDARD_HOST',
        'user': os.getenv('APACHE_LIBCLOUD_ACCOUNT'),
        'key': os.getenv('APACHE_LIBCLOUD_SECRET_KEY'),
        'bucket': 'trww-rainfall-reports',
        'region': 'us-east-2'
    }
}

DEFAULT_LIBCLOUD_PROVIDER = 'trww_rainfall_reports'

# django-cloud-browser
# see documentation for Django-Cloud-Browser for explanation of environment 
# variables: https://ryan-roemer.github.io/django-cloud-browser

CLOUD_BROWSER_DATASTORE = 'ApacheLibcloud'
CLOUD_BROWSER_APACHE_LIBCLOUD_PROVIDER = os.getenv('APACHE_LIBCLOUD_PROVIDER', "S3")
CLOUD_BROWSER_APACHE_LIBCLOUD_ACCOUNT = os.getenv('APACHE_LIBCLOUD_ACCOUNT')
CLOUD_BROWSER_APACHE_LIBCLOUD_SECRET_KEY = os.getenv('APACHE_LIBCLOUD_SECRET_KEY')

CLOUD_BROWSER_CONTAINER_WHITELIST = ['trww-rainfall-reports']
CLOUD_BROWSER_VIEW_DECORATOR = "django.contrib.admin.views.decorators.staff_member_required"
'''

# ------------------------------------------------------------------------------
# LOGGING

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': ('%(asctime)s [%(process)d] [%(levelname)s] '
                       'pathname=%(pathname)s lineno=%(lineno)s '
                       'funcname=%(funcName)s %(message)s'),
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'simple': {
            'format': '%(levelname)s %(message)s'
        }
    },
    'handlers': {
        'null': {
            'level': 'DEBUG',
            'class': 'logging.NullHandler',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        }
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    }
}


# ------------------------------------------------------------------------------
# Django Debug Toolbar (configure for use with Docker)

DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': lambda request: DEBUG,
}

