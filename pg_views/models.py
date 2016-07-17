import sys

from collections import OrderedDict

from django.utils import six
from django.db import connection, models
from django.utils.translation import ugettext

from .loading import register_sql_model_view, get_sql_model_view


class DBViewBase(type):

    def __new__(cls, *args, **kwargs):
        name, _, attrs = args
        abstract = attrs.pop('abstract', False)
        super_new = super(DBViewBase, cls).__new__
        new_class = super_new(cls, *args, **kwargs)
        model_module = sys.modules[new_class.__module__]
        app_label = model_module.__name__.split('.')[-2]
        if name != 'NewBase' and not abstract:
            register_sql_model_view(app_label, new_class)
        return new_class


class DBView(six.with_metaclass(DBViewBase)):
    abstract = True
    view_name = None
    upper_names = True

    def get_columns(self):
        return OrderedDict()

    def get_name(self):
        return self.upper_names and self.view_name.upper() or self.view_name

    def get_condition(self):
        return None


class ModelDBView(DBView):
    abstract = True
    model = None
    exclude = ()
    fields = None
    column_name_mapping = {}

    def get_field_db_type(self, field):
        field_db_type = field.db_type(connection).split('CHECK')[0].strip()
        return 'integer' if field_db_type == 'serial' else field_db_type

    def get_column_name(self, model_column_name):
        column_name = self.column_name_mapping.get(model_column_name, model_column_name)
        return self.upper_names and column_name.upper() or column_name

    def get_columns(self):
        result = super(ModelDBView, self).get_columns()
        for field in self.model._meta.fields:
            attname, column = field.get_attname_column()
            if attname not in self.exclude and (self.fields is None or field.name in self.fields):
                verbose_name = field.verbose_name
                if isinstance(field, models.ForeignKey) and get_sql_model_view(field.rel.to):
                    verbose_name = '{} ({} {})'.format(verbose_name, ugettext('foreign key to view'),
                                                       get_sql_model_view(field.rel.to)().get_name())
                result[self.get_column_name(column)] = (column, verbose_name, self.get_field_db_type(field))
        return result

    def get_name(self):
        name = self.view_name or '%s_view' % self.model._meta.db_table
        return self.upper_names and name.upper() or name
