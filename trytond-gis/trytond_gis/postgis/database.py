# This file is part of trytond_gis.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import binascii

from geomet import wkb
from psycopg2.extensions import (register_adapter, new_type, register_type,
    Binary)

from trytond.backend.postgresql.database import Database as PGDatabase

from trytond_gis import _GeoJSON


def ewkb2geojson(value, cursor):
    if value is None:
        return None
    return wkb.loads(binascii.a2b_hex(value))


class Database(PGDatabase):

    _GIS_OIDS = None

    @classmethod
    def create(cls, connection, database_name):
        super(Database, cls).create(connection, database_name)

        database = cls(database_name)
        with database.get_connection() as db_connection:
            cursor = db_connection.cursor()
            cursor.execute("CREATE EXTENSION postgis")

    def get_connection(self, autocommit=False, readonly=False):
        conn = super(Database, self).get_connection(autocommit, readonly)

        if self._GIS_OIDS is None:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM pg_extension WHERE extname='postgis'")
            if cursor.fetchone():
                cursor.execute('SELECT NULL::geometry, NULL::geography')
                geometry_oid = cursor.description[0][1]
                geography_oid = cursor.description[1][1]
                self._GIS_OIDS = {
                    'geometry': geometry_oid,
                    'geography': geography_oid,
                    }

                GEOMETRY = new_type((geometry_oid,), 'GEOMETRY', ewkb2geojson)
                register_type(GEOMETRY)
                GEOGRAPHY = new_type(
                    (geography_oid,), 'GEOGRAPHY', ewkb2geojson)
                register_type(GEOGRAPHY)

        return conn


register_adapter(_GeoJSON, lambda value: Binary(wkb.dumps(value)))
