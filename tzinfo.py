#!/bin/python3
from datetime import datetime, timedelta, tzinfo

class TimeZone(tzinfo):
    def __init__(self, offset, isdst, name):
        self.offset = offset
        self.isdst = isdst
        self.name = name
    def utcoffset(self, dt):
        return timedelta(hours=self.offset) + self.dst(dt)
    def dst(self, dt):
        return timedelta(hours=1) if self.isdst else timedelta(0)
    def tzname(self,dt):
        return self.name
    def fromutc(self, dt):
        dtoff = dt.utcoffset()
        dtdst = dt.dst()
        std_delta = dtoff - dtdst
        if std_delta:
            dt += std_delta
            dtdst = dt.dst()
        if dtdst:
            return dt + dtdst
        else:
            return dt

tz = TimeZone(8,False,'UTC+8')

retentionDate = datetime.now(tz) - timedelta(days=1)
print (datetime.utcnow())
print (datetime.now(tz))
print (retentionDate)
print (datetime.now(tz).replace(1987,tzinfo=None))
print (datetime.now(tz).replace(1987))

