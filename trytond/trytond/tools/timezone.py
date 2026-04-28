# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import os
import zoneinfo

ZoneInfo = zoneinfo.ZoneInfo
ZoneInfoNotFoundError = zoneinfo.ZoneInfoNotFoundError

__all__ = ['SERVER', 'UTC', 'get_tzinfo', 'available_timezones']
logger = logging.getLogger(__name__)
_ALL_ZONES = None


def available_timezones():
    global _ALL_ZONES

    if not _ALL_ZONES:
        _ALL_ZONES = zoneinfo.available_timezones()
    return set(_ALL_ZONES)


def get_tzinfo(zoneid):
    try:
        zi = ZoneInfo(zoneid)
        if not zi:
            raise ZoneInfoNotFoundError
    except ZoneInfoNotFoundError:
        logger.warning("Timezone %s not found falling back to UTC", zoneid)
        zi = UTC
    return zi


UTC = ZoneInfo('UTC')
SERVER = get_tzinfo(os.environ['TRYTOND_TZ'])
