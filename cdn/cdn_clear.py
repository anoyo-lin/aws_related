#!/usr/bin/python3
import boto3
import datetime
import subprocess,shlex
from botocore.exceptions import ClientError
import os,sys
import threading
import re

region = os.environ.get('REGION_NAME', None)
if region == None:
    region = 'eu-west-1'
retention = int(os.environ.get('RETENTION', 0))
if retention == 0:
    retention = 365
profile = None
bucket = os.environ.get('LOG_BUCKET', None)
if bucket == None:
    bucket = 'redacted'
app = os.environ.get('APP_LIST', '').split(',')
if app == ['']:
    app = ['redacted']
dt = os.environ.get('START_DATE', '').split('-')
if dt == ['']:
    start_date = datetime.datetime(2017,8,1)
elif len(dt) != 3:
    print ('please key-in correct START_DATE, eg: 2017-08-01')
    sys.exit(-1)
else:
    start_date = datetime.datetime(int(dt[0]), int(dt[1]), int(dt[2]))
today = datetime.datetime.now()
end_date = today - datetime.timedelta(retention)
date_pool = list()
while start_date <= end_date:
        date_prefix = 'logyear={0}/logmonth={1}/logday={2}'.format(start_date.strftime('%Y'), start_date.strftime('%m'), start_date.strftime('%d'))
        date_pool.append(date_prefix)
        start_date += datetime.timedelta(1)

class ProgressPercentage(object):
        def __init__(self, filename):
            self._filename = filename
            self._size = float(os.path.getsize(filename))
            self._seen_so_far = 0
            self._lock = threading.Lock()

        def __call__(self, bytes_amount):
            # To simplify we'll assume this is hooked up
            # to a single filename.
            with self._lock:
                self._seen_so_far += bytes_amount
                percentage = (self._seen_so_far / self._size) * 100
                sys.stdout.write(
                    "\r%s  %s / %s  (%.2f%%)" % (
                        self._filename, self._seen_so_far, self._size,
                        percentage))
                sys.stdout.flush()

def lst_object(app_name, date_prefix=date_prefix, Bucket='cdn-log-statistics'):
    Prefix = '{0}/{1}/'.format(app_name, date_prefix)
    session = boto3.Session(profile_name = profile)
    s3_client = session.client('s3', region_name = region)
    try:
        response = s3_client.list_objects_v2(
                Bucket = Bucket,
                Prefix = Prefix
                )
    except ClientError as e:
        print ('Unexpected Error: {0}'.format(e))
    return response

def main():
    remove_lst=list()
    for date_prefix in date_pool:
        for app_name in app:
            if 'Contents' not in lst_object(app_name + '_cdn_logs', Bucket=bucket, date_prefix=date_prefix):
                continue
            for content in lst_object(app_name + '_cdn_logs', Bucket=bucket, date_prefix=date_prefix)['Contents']:
                remove_lst.append({
                    'Key': content['Key'],
                    })
                    
    s3_client.delete_objects(
            Bucket=bucket,
            Delete={
                'Objects': remove_lst,
                'Quiet': False
                }
            )
def lambda_handler(event, context):
    main()

#lambda_handler('event', 'context')
