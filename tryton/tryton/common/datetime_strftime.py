# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# Copyright (c) 2002-2007 John D. Hunter; All Rights Reserved
import time


def datetime_strftime(dt, fmt):
    '''
    Allow datetime strftime formatting for years before 1900.
    See http://bugs.python.org/issue1777412
    '''
    if dt.year > 1900:
        return dt.strftime(fmt)

    def _findall(text, substr):
        # Also finds overlaps
        sites = []
        i = 0
        while True:
            j = text.find(substr, i)
            if j == -1:
                break
            sites.append(j)
            i = j + 1
        return sites

    year = dt.year
    # For every non-leap year century, advance by
    # 6 years to get into the 28-year repeat cycle
    delta = 2000 - year
    off = 6 * (delta // 100 + delta // 400)
    year = year + off
    # Move to around the year 2000
    year = year + ((2000 - year) // 28) * 28
    timetuple = dt.timetuple()
    s1 = time.strftime(fmt, (year,) + timetuple[1:])
    sites1 = _findall(s1, str(year))

    s2 = time.strftime(fmt, (year + 28,) + timetuple[1:])
    sites2 = _findall(s2, str(year + 28))

    sites = []
    for site in sites1:
        if site in sites2:
            sites.append(site)

    s = s1
    syear = "%04d" % (dt.year,)
    for site in sites:
        s = s[:site] + syear + s[site + 4:]
    return s
