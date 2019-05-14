#!/usr/bin/python3
import boto3
import datetime
import subprocess,shlex
from botocore.exceptions import ClientError
import os,sys
import threading
import re

interval = int(os.environ.get('THRESHOLD', 0))
if interval == 0:
    interval = 200
retention = int(os.environ.get('RETENTION', 0))
if retention == 0:
    retention = 27 
region = os.environ.get('REGION_NAME', None)
if region == None:
    region = 'eu-west-1'
profile = None
bucket = os.environ.get('LOG_BUCKET', None)
if bucket == None:
    bucket = 'redacted'
app = os.environ.get('APP_LIST', '').split(',')
if app == ['']:
    app = ['redacted']

#start_date = datetime.datetime(2018,4,19)
end_date = datetime.date.today()
start_date = end_date - datetime.timedelta(retention)
temp_date = start_date

date_pool = list()
while start_date <= temp_date:
        date_prefix = 'logyear={0}/logmonth={1}/logday={2}'.format(start_date.strftime('%Y'), start_date.strftime('%m'), start_date.strftime('%d'))
        date_pool.append(date_prefix)
        start_date += datetime.timedelta(1)

#year = (datetime.date.today() - datetime.timedelta(retention)).strftime('%Y')
#month = (datetime.date.today() - datetime.timedelta(retention)).strftime('%m')
#day = (datetime.date.today() - datetime.timedelta(retention)).strftime('%d')
#date_prefix = 'logyear={0}/logmonth={1}/logday={2}'.format(year, month, day)

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

def replace_imei(local_file, app):
#   zcat_log = subprocess.Popen('zcat {0}'.format(local_file), shell=True, stdout=subprocess.PIPE)
#   sed_imei = subprocess.Popen("sed 's/IMEI=[0-9]*&/IMEI=FIXED&/g'", shell=True, stdin=zcat_log.stdout, stdout=subprocess.PIPE)
#   with open(local_file+'.tmp', 'w') as zip_file:
#       zip_log = subprocess.Popen('gzip -c', shell=True, stdin=sed_imei.stdout, stdout=zip_file)
#   output = zip_log.communicate()[0]
#   subprocess.check_output("zcat {0} | sed 's/IMEI=[0-9]*\&/IMEI=GDPR_REMOVED\&/g' | gzip -c > {1}".format(local_file, local_file+'.tmp'), shell=True)
#   subprocess.check_call('mv {0} {1}'.format(local_file+'.tmp', local_file), shell=True)
#   subprocess.check_output("zcat {0} | sed 's/\\(^[^ ]* [^ ]* [^ ]* \\)[^ ]*\\(.*\\)/\\1GDPR_REMOVED\\2/; s/IMEI=[0-9]*\\&/IMEI=GDPR_REMOVED\\&/g; s/imei=[0-9]*\\&/imei=GDPR_REMOVED\\&/g;' | gzip -c > {1}".format(local_file, local_file+'.tmp'), shell=True)
    devid_cmd = "zcat {0} | sed 's/\\(^[^ ]* [^ ]* [^ ]* \\)[^ a-zA-Z]* /\\1GDPR_REMOVED /; s/\\(devId=\\)[^&]*\\&/\\1GDPR_REMOVED\\&/g' | gzip -c > {1}".format(local_file, local_file+'.tmp')
    imei_cmd =  "zcat {0} | sed 's/\\(^[^ ]* [^ ]* [^ ]* \\)[^ a-zA-Z]* /\\1GDPR_REMOVED /; s/\\([Ii][Mm][Ee][Ii]=\\)[^&]*\\&/\\1GDPR_REMOVED\\&/g' | gzip -c > {1}".format(local_file, local_file+'.tmp')
    def_cmd = "zcat {0} | sed 's/\\(^[^ ]* [^ ]* [^ ]* \\)[^ a-zA-Z]* /\\1GDPR_REMOVED /;' | gzip -c > {1}".format(local_file, local_file+'.tmp')
    if app == 'fuas' or app == 'releasenotes':
        print (devid_cmd)
        subprocess.check_output(devid_cmd, shell=True)
    elif app == 'uep' or app == 'emma':
        print (imei_cmd)
        subprocess.check_output(imei_cmd, shell=True)
    else:
        print (def_cmd)
        subprocess.check_output(def_cmd, shell=True)

    subprocess.check_call('mv {0} {1}'.format(local_file+'.tmp', local_file), shell=True)
    return 'Already Mask Completed: Local File {0}'.format(local_file)


def main(Bucket=bucket):
    start = datetime.datetime.now()
    for date_prefix in date_pool:
        for app_name in app:
            if 'Contents' not in lst_object(app_name + '_cdn_logs', Bucket=bucket, date_prefix=date_prefix):
                continue
#           pool += lst_object(app_name, Bucket=bucket, date_prefix=date_prefix)['Contents']
#       if pool == []:
#           return "no record!"
            for content in lst_object(app_name + '_cdn_logs', Bucket=bucket, date_prefix=date_prefix)['Contents']:
                re_name = re.compile('.*\.log\.gz$')
                type_name = re.compile('^STANDARD.*')
                if end_date - content['LastModified'].date() > datetime.timedelta(days=0) and type_name.search(content['StorageClass']) and re_name.search(content['Key'].split('/')[4]):
#                if type_name.search(content['StorageClass']) and re_name.search(content['Key'].split('/')[4]):
                    local_file='/tmp/' + content['Key'].split('/')[4]
                    try:
                        session = boto3.Session(profile_name = profile)
                        s3_client = session.client('s3', region_name = region)
                        s3_config = boto3.s3.transfer.TransferConfig(
                            multipart_threshold=30*1024*1024,
                            max_concurrency=20,
                            multipart_chunksize=10*1024*1024,
                            num_download_attempts=10,
                            max_io_queue=100,
                            io_chunksize=5*1024*1024,
                            use_threads=True
                            )
                        s3_trans = boto3.s3.transfer.S3Transfer(client = s3_client)
                        s3_trans.download_file(Bucket, content['Key'], local_file)
                        print ('download from {0}'.format(content['Key']), replace_imei(local_file, app_name))
                        s3_trans.upload_file(local_file, Bucket, content['Key'], extra_args={'StorageClass': 'STANDARD_IA'}, callback=ProgressPercentage(local_file))
                        print ('\n')
                        os.remove(local_file)
                    except Exception as e:
                        print ('Error: %s' % (e,))
                    stop = datetime.datetime.now()
                    if round((stop-start).total_seconds())//interval >= 1:
                        return 'exceed {0} seconds, exit!'.format(interval)
def lambda_handler(event, context):
    print (main(Bucket=bucket))

#lambda_handler('event', 'context')

