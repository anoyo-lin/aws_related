#!/usr/bin/python3
import paramiko
import boto3
import datetime
import time
import re
from io import StringIO
import os, sys

#in case there are unsent logs leave behind near dayend time.
day = int(os.environ.get('DAY', 0))
day_end = int(os.environ.get('DAY_END', 0))
if day_end == 0:
    day_end = 3
threshold = int(os.environ.get('THRESHOLD', 0))
if threshold == 0:
    threshold = 200
region_name = os.environ.get('REGION_NAME', None)
if region_name == None:
    region_name = 'eu-west-1'
key_bucket = os.environ.get('KEY_BUCKET', None)
if key_bucket == None:
    key_bucket = 'redacted'
key_path = os.environ.get('KEY_PATH', None)
if key_path == None:
    key_path = 'redacted'
log_bucket = os.environ.get('LOG_BUCKET', None)
if log_bucket == None:
    log_bucket = 'redacted'
athena_db = os.environ.get('ATHENA_DB', None)
if athena_db == None:
    athena_db = 'edgecast_logs'
cdn_list = [ app_list.split(',') for app_list in os.environ.get('CDN_LIST', '').split(';')] 
if cdn_list == [['']]:
    cdn_list = [
            ['url', 'user', 'app_name']
            ]
else:
    for app_list in cdn_list:
        if len(app_list) != 3:
            print ("wrong cdn list please enter with specified format in 'url,user_name,athena_query_table'")
            sys.exit(-1)
profile = None
if datetime.datetime.now().time() < datetime.time(day_end, 00, 00, 000000):
    retention = 1 + day 
else:
    retention = 0 + day

year = (datetime.date.today() - datetime.timedelta(retention)).strftime('%Y')
month = (datetime.date.today() - datetime.timedelta(retention)).strftime('%m')
day = (datetime.date.today() - datetime.timedelta(retention)).strftime('%d')

print (day_end, threshold, region_name, key_bucket, key_path, log_bucket, athena_db, cdn_list, profile, year + month + day)

def aws_init(method, module, profile_name):
    session = boto3.Session(profile_name = profile_name)
    if method == 'resource':
        ec2_res = session.resource(module)
        return ec2_res
    else:
        ec2_client = session.client(module)
        return ec2_client

#paramiko.util.log_to_file("/tmp/paramiko.log")
def connect_to_sftp(hostname, port, username, password, pkey):
    transport = paramiko.Transport((hostname, port))
#   https://github.com/paramiko/paramiko/issues/175
    transport.window_size = 2147483647
    transport.packetizer.REKEY_BYTES = pow(2, 40)
    transport.packetizer.REKEY_PACKETS = pow(2, 40)
    if pkey:
        transport.connect(username=username, pkey=pkey)
    else:
        transport.connect(username=username, password=password)
    client = paramiko.SFTPClient.from_transport(transport)
    return client, transport
#obsolete
def transfer_files(sftp_client, s3_path, filename, bucket):
    session = boto3.Session(profile_name = profile)
    s3_res = session.resource('s3', region_name = region_name)

    sftp_client.chdir(path='/logs/')
    with sftp_client.open(filename, 'r') as sftp_file:
        s3_res.Object(bucket, s3_path+filename).put(Body = sftp_file)
    return 'put the %s to %s' % (filename, bucket+'/'+s3_path+filename)

def transfer_to_local(sftp_client, s3_path, filename, bucket):
    sftp_client.chdir(path = '/logs/')
    sftp_client.get(filename, '/tmp/' + filename)
    print ('sftp tranferred ok')
#   https://boto3.readthedocs.io/en/latest/reference/customizations/s3.html#boto3.s3.transfer.TransferConfig
    try:
        s3_config = boto3.s3.transfer.TransferConfig(
            multipart_threshold=30*1024*1024,
            max_concurrency=20,
            multipart_chunksize=10*1024*1024,
            num_download_attempts=10,
            max_io_queue=100,
            io_chunksize=5*1024*1024,
            use_threads=True
            )
        session = boto3.Session(profile_name = profile)
        s3_client = session.client('s3', region_name = region_name)

        s3_trans = boto3.s3.transfer.S3Transfer(client = s3_client, config = s3_config)
        s3_trans.upload_file('/tmp/' + filename, bucket, s3_path + filename)
    except Exception as e:
        print ('Error: %s' % (e,))
    os.remove('/tmp/' + filename)
    return 'put the %s to %s' % (filename, bucket+'/'+s3_path+filename)

def get_pkey(bucket, key, key_type='RSA'):
    session = boto3.Session(profile_name = profile)
    s3_res = session.resource('s3', region_name = region_name)

    s3_obj = s3_res.Object(bucket, key)
    pkey_str = s3_obj.get()['Body'].read().decode('utf-8')
    if key_type == 'DSA':
        pkey = paramiko.DSSKey.from_private_key(StringIO(pkey_str))
    else:
        pkey = paramiko.RSAKey.from_private_key(StringIO(pkey_str))
    return pkey

def load_partition(tbl_name = 'test', db_name = 'gene', bucket = 'test'):
    session = boto3.Session(profile_name = profile)
    athena = session.client('athena', region_name = region_name)
#    query = 'MSCK REPAIR TABLE %s;' % (tbl_name,)
    query = "ALTER TABLE {0} ADD IF NOT EXISTS PARTITION (logyear='{1}',logmonth='{2}',logday='{3}') location 's3://{5}/{4}/logyear={1}/logmonth={2}/logday={3}/';".format(tbl_name, year, month, day, tbl_name + '_cdn_logs', bucket)
    response = athena.start_query_execution(
    QueryString = query,
    QueryExecutionContext = {
        'Database': db_name
        },
    ResultConfiguration = {
        'OutputLocation': 's3://%s/%s/Load_Partitions/%s/' % (bucket, tbl_name + '_cdn_logs', year + month + day)
        },
    )
    query_id = response['QueryExecutionId']
    while 1:
        get_query = athena.get_query_execution(QueryExecutionId = query_id)
        state = get_query['QueryExecution']['Status']['State']
        if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            print ('load_partition state: %s, completed! ' % state)
            return athena.get_query_results(QueryExecutionId = query_id)
            #time.sleep(3)
            #s3 = session.client('s3', region_name = region_name)
            #s3.delete_object(
            #        Bucket = bucket,
            #        Key = tbl_name + '/' + 'Load_Partitions' + '/' + year + month + day + '/' + query_id + '.txt.metadata',
            #        )
            break
        else:
            print ('load_partition state: %s, waiting for completed! ' % state)
            time.sleep(3)

def sftp_to_s3(hostname, port, username, key_bucket, key_path, log_bucket, athena_db, athena_tbl, start):

#    start = datetime.datetime.now()

    s3_path = athena_tbl + '_cdn_logs' + '/' + 'logyear=' + str(year) + '/' + 'logmonth=' + str(month) + '/' + 'logday=' + str(day) + '/'

    pkey = get_pkey(key_bucket, key_path)
#    if hostname == 'redacted':
#        sftp_client, transport = connect_to_sftp(hostname, port, 'redacted', 'password', None)
#    else:
    sftp_client, transport = connect_to_sftp(hostname, port, username, None, pkey)
    sftp_client.chdir(path='/logs/')
    pattern = str(year + month + day)
    re_pattern = re.compile(pattern)
    selected_logs = set(item for item in sftp_client.listdir() if re_pattern.search(item))

    session = boto3.Session(profile_name = profile)
    s3_client = session.client('s3', region_name = region_name)

    response = s3_client.list_objects_v2(
            Bucket = log_bucket,
            Prefix = s3_path
            )
#    for item in selected_logs:
#        print (sftp_client.open(item, 'r').stat())
    transferred = set()
    if 'Contents' in response:
        transferred = set(content['Key'].split('/')[4] for content in response['Contents'])
    corrupted = set()
    for item in transferred:
        if item in selected_logs:
            src = sftp_client.lstat(path=item).st_size
            dest = s3_client.head_object(Bucket=log_bucket, Key=s3_path + item)['ContentLength']
            if src != dest:
                corrupted.add(item)
        else:
            s3_client.delete_object(Bucket=log_bucket, Key=s3_path + item)

    residue = selected_logs - transferred | corrupted
    if len(residue) == 0:
        sftp_client.close()
        #load_resp = s3_client.list_objects_v2(
        #        Bucket = log_bucket,
        #        Prefix = '%s/Load_Partitions/%s/' % (athena_tbl, year + month + day)
        #        )
        #if 'Contents' in load_resp:
        #    return 'already load_partition before'
        #else:
#        load_partition(tbl_name = athena_tbl, db_name = athena_db, bucket = log_bucket)
        print ('{0} sync successfully'.format(athena_tbl))
        return 1
    else:
        for item in residue:
            print (transfer_to_local(sftp_client, s3_path, item, log_bucket))
            stop = datetime.datetime.now()
            if round((stop-start).total_seconds())//threshold >= 1:
                sftp_client.close()
                load_partition(tbl_name = athena_tbl, db_name = athena_db, bucket = log_bucket)
                print ('{1} exceed {0} seconds, quit!'.format(threshold, athena_tbl))
                return -1
        sftp_client.close()
        load_partition(tbl_name = athena_tbl, db_name = athena_db, bucket = log_bucket)
        print ('{0} upload&load complete'.format(athena_tbl))
        return 0

def lambda_handler(event, context):
    start = datetime.datetime.now()
    for cdn in cdn_list:
        response = sftp_to_s3(cdn[0], 22, cdn[1], key_bucket, key_path, log_bucket, athena_db, cdn[2], start)
        if response == -1:
            break
#lambda_handler('event', 'context')
