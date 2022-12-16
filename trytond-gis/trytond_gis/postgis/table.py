# This file is part of trytond_gis.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from trytond.config import config
from trytond.transaction import Transaction
from trytond.backend.postgresql.table import TableHandler as PGTableHandler

from trytond_gis.const import GIS_SQL_TYPE_RE, WGS_84

logger = logging.getLogger(__name__)


class TableHandler(PGTableHandler):

    def add_column(self, column_name, abstract_type, default=None, comment=''):
        if abstract_type.startswith('GIS_'):
            column_adder = self.add_geometry_column
        else:
            column_adder = super(TableHandler, self).add_column
        column_adder(column_name, abstract_type, default, comment)

    def add_geometry_column(self, column_name, abstract_type, default_fun=None,
            fill_default=True, comment=''):
        cursor = Transaction().connection.cursor()

        match = GIS_SQL_TYPE_RE.match(abstract_type)
        assert match is not None, \
            'The abstract type %s is not supported' % abstract_type
        type_ = match.group('type')
        srid = config.getint('database', 'srid', default=WGS_84)
        dimension = int(match.group('dimension'))

        if self.column_exist(column_name):
            cursor.execute('''
                SELECT type, srid, coord_dimension
                FROM geometry_columns
                WHERE f_table_name=%s and f_geometry_column=%s''',
                (self.table_name, column_name))
            column_info = cursor.fetchone()
            if not column_info:
                logger.warning(
                    'Unable to migrate column %s on table %s '
                    'column is not a geometric type.',
                    column_name, self.table_name)
                return

            prev_type, prev_srid, prev_dimension = column_info
            if prev_type.upper() != type_.upper():
                logger.warning(
                    'Unable to migrate column %s on table %s '
                    'from %s to %s.',
                    column_name, self.table_name,
                    prev_type, type_)
            elif prev_srid != srid:
                logger.warning(
                    'Unable to migrate column %s on table %s '
                    'from SRID %s to %s.',
                    column_name, self.table_name,
                    prev_srid, srid)
            elif prev_dimension != dimension:
                logger.warning(
                    'Unable to migrate column %s on table %s '
                    'from dimension %s to %s.',
                    column_name, self.table_name,
                    prev_dimension, dimension)
            return

        cursor.execute('SELECT AddGeometryColumn(%s, %s, %s, %s, %s)',
            (self.table_name, column_name, srid, type_, dimension))
        self._update_definitions(columns=True)
