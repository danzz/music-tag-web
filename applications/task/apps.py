from django.apps import AppConfig
from django.db.backends.signals import connection_created
from django.db.models.signals import post_migrate

from applications.task.handlers import init_task


def configure_sqlite_connection(sender, connection, **kwargs):
    if connection.vendor == 'sqlite':
        try:
            with connection.cursor() as cursor:
                cursor.execute('PRAGMA journal_mode = WAL;')
                cursor.execute('PRAGMA synchronous = NORMAL;')
                cursor.execute('PRAGMA busy_timeout = 10000;')
        except Exception:
            pass


class ProjectConfig(AppConfig):
    name = 'applications.task'

    def ready(self):
        post_migrate.connect(init_task, self)
        connection_created.connect(configure_sqlite_connection)

