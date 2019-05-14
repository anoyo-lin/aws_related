#!/usr/bin/python3
import boto3
from datetime import datetime, timedelta, tzinfo
import re

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

tz = TimeZone(0,False,'UTC+0')

therashold = datetime(2018,1,1,0,0,0,0,tz)
session = boto3.Session()
s3_client = session.client('s3')
for bucket_lst in s3_client.list_buckets()['Buckets']:
    bucket_contents = s3_client.list_objects_v2(Bucket = bucket_lst['Name'])
    if 'Contents' in bucket_contents:
        for objects in bucket_contents['Contents']:
            if objects['LastModified'] < therashold:
                if re.search('.*[^\/]$', objects['Key']):
                    print ('s3://{}/{}'.format(bucket_lst['Name'],objects['Key']))
