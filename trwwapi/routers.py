from django.apps import apps

# class ModelDatabaseRouter:
#     """Allows each model to set its own destiny"""

#     def db_for_read(self, model, **hints):
#         # Specify target database with field in_db in model's Meta class
#         return getattr(model._meta, 'in_db', None)

#     def db_for_write(self, model, **hints):
#         # Specify target database with field in_db in model's Meta class
#         return getattr(model._meta, 'in_db', None)

#     def allow_migrate(self, db, app_label, model_name=None, **hints):
#         # if in_db is specified and matches db, use that for migration,
#         # otherwise use default
#         # print(db, app_label, model_name)
#         if model_name is None:
#             return None
#         model = apps.get_model(app_label, model_name)
#         db_name = getattr(model._meta, 'in_db', None)
#         if db_name is not None:
#             return db_name == db
#         return None

class RainfallDbRouter:

    route_app_labels = {'rainfall'}
    rainfall_db = 'rainfall_db'

    def db_for_read(self, model, **hints):
        """
        Attempts to read rainfall models go to rainfall_db.
        """
        if model._meta.app_label in self.route_app_labels:
            return 'rainfall_db'
        return 'default'

    def db_for_write(self, model, **hints):
        """
        Attempts to write rainfall models go to rainfall_db.
        """
        if model._meta.app_label in self.route_app_labels:
            return 'rainfall_db'
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations if a model in the rainfall app is
        involved.
        """
        if (
            obj1._meta.app_label in self.route_app_labels or
            obj2._meta.app_label in self.route_app_labels
        ):
           return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Make sure the rainfall app only appears in the
        'rainfall' database.
        """
        # print(db, app_label, model_name)
        if app_label in self.route_app_labels:
            return db == self.rainfall_db
        return None


class DefaultRouter:

    def db_for_read(self, model, **hints):
        return 'default'

    def db_for_write(self, model, **hints):
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return True