# This file is part of trytond_gis.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import binascii
from functools import cache

from geomet import wkb
from psycopg.adapt import Dumper, Loader
from psycopg.postgres import adapters
from psycopg.pq import Format
from psycopg.types import TypeInfo

from trytond.backend.postgresql.database import Database as PGDatabase
from trytond.config import parse_uri
from trytond_gis import _GeoJSON


class GeometryBinaryLoader(Loader):
    format = Format.BINARY

    def load(self, data):
        return wkb.loads(binascii.a2b_hex(data))


class GeometryLoader(Loader):
    def load(self, data):
        return wkb.loads(binascii.a2b_hex(data))


class BaseGeometryBinaryDumper(Dumper):
    format = Format.BINARY

    def dump(self, obj):
        return wkb.dumps(obj)


class BaseGeometryDumper(Dumper):
    def dump(self, obj):
        return wkb.dumps(obj).encode()


class Database(PGDatabase):

    _GIS_OIDS = None

    @classmethod
    def create(cls, connection, database_name):
        super().create(connection, database_name)

        database = cls(database_name)
        with database.get_connection() as db_connection:
            cursor = db_connection.cursor()
            cursor.execute("CREATE EXTENSION postgis")

    @classmethod
    def _connection_params(cls, name):
        params = super()._connection_params(name)
        uri = parse_uri(params['conninfo'])
        params['conninfo'] = uri._replace(scheme='postgresql').geturl()
        return params

    def get_connection(
            self, autocommit=False, readonly=False, statement_timeout=None):
        conn = super().get_connection(
            autocommit=autocommit, readonly=readonly,
            statement_timeout=statement_timeout)

        if self._GIS_OIDS is None:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM pg_extension WHERE extname='postgis'")
            if cursor.fetchone():
                geometry_info = TypeInfo.fetch(conn, 'geometry')
                geometry_info.register()

                adapters.register_loader(
                    geometry_info.oid, GeometryBinaryLoader)
                adapters.register_loader(geometry_info.oid, GeometryLoader)

                adapters.register_dumper(
                    _GeoJSON, _make_dumper(geometry_info.oid))
                adapters.register_dumper(
                    _GeoJSON, _make_binary_dumper(geometry_info.oid))

                self._GIS_OIDS = {
                    'geometry': geometry_info.oid,
                    }
        return conn


@cache
def _make_dumper(oid_in):
    class GeometryDumper(BaseGeometryDumper):
        oid = oid_in

    return GeometryDumper


@cache
def _make_binary_dumper(oid_in):
    class GeometryBinaryDumper(BaseGeometryBinaryDumper):
        oid = oid_in

    return GeometryBinaryDumper
