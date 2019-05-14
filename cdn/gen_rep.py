#!/usr/bin/python3
import boto3
import datetime
import time
import sys, os

profile = None
retention = int(os.environ.get('RETENTION', -1))
if retention == -1:
    retention = 1
region = os.environ.get('REGION_NAME', None)
if region == None:
    region = 'eu-west-1'
athena_db = os.environ.get('ATHENA_DB', None)
if athena_db == None:
    athena_db = 'edgecast_logs'
cdn_lst = os.environ.get('APP_LIST', '').split(',')
if cdn_lst == ['']:
    cdn_lst = ['redacted']
log_bucket = os.environ.get('LOG_BUCKET', None)
if log_bucket == None:
    log_bucket = 'redacted'
topic = ' & '.join(cdn_lst)
mail_list = os.environ.get('MAIL_LIST', '').split(',')
if mail_list == ['']:
    mail_list = ['test@test.com']
sender_addr = os.environ.get('SENDER_ADDR', None)
if sender_addr == None:
    sender_addr = 'test@test.com'

year = (datetime.date.today() - datetime.timedelta(retention)).strftime('%Y')
month = (datetime.date.today() - datetime.timedelta(retention)).strftime('%m')
day = (datetime.date.today() - datetime.timedelta(retention)).strftime('%d')

def aws_init(method, module, profile_name, region_name):
    session = boto3.Session(profile_name = profile_name)
    if method == 'resource':
        ec2_res = session.resource(module, region_name = region_name)
        return ec2_res
    else:
        ec2_client = session.client(module, region_name = region_name)
        return ec2_client
# it doesnt need run load_partition in athena sql statistics generating procedure, i had just optimized it at sftp transfer phase, no need for this function. and
# msck repair partition will scan every parition for correcting error function, and it cost a lot time if the partition quantities grow too huge, so it needs another method
# alter table add partition method to handle it
def load_partition(tbl_name = 'redacted', db_name = 'gene', bucket = 'est'):
    session = boto3.Session(profile_name = profile)
    athena = session.client('athena', region_name = region)
    query = 'MSCK REPAIR TABLE %s;' % (tbl_name,)
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
            #session = boto3.Session(profile_name = profile)
            #s3 = session.client('s3', region_name = region)
            #s3.delete_object(
            #        Bucket = bucket,
            #        Key = tbl_name + '/' + 'Load_Partitions' + '/' + year + month + day + '/' + query_id + '.txt.metadata',
            #        )
            break
        else:
            print ('load_partition state: %s, waiting for completed! ' % state)
            time.sleep(3)
# an athena function can query the wanted result from apache hive
# in SQL launage as paraphase means you can create an alias for one sentence you ignore the alias after word 'as'
# select from a table that can customize all by yourself
def http_code(tbl_name = 'test', db_name = 'gene', bucket = 'test'):
    query = """SELECT httpstatus AS HTTP_CODE, NRREQUESTS, 100.0*NRREQUESTS/TOTAL_REQUESTS AS RATIO FROM(
            SELECT httpstatus, count(*) AS NRREQUESTS, (SELECT count(*) FROM %(tbl_name)s WHERE logyear='%(year)s' AND logmonth='%(month)s' AND logday='%(day)s') AS TOTAL_REQUESTS FROM %(tbl_name)s WHERE logyear='%(year)s' AND logmonth='%(month)s' AND logday='%(day)s' GROUP BY httpstatus ORDER BY httpstatus DESC 
            ) AS result ORDER BY httpstatus""" % { 'year': year, 'month': month, 'day': day, 'tbl_name': tbl_name }
    session = boto3.Session(profile_name = profile)
    athena = session.client('athena', region_name = region)
    response = athena.start_query_execution(
            QueryString = query,
            QueryExecutionContext = {
                'Database': db_name
                },
            ResultConfiguration = {
                'OutputLocation': 's3://%s/%s/Results/%s/' % (bucket, tbl_name + '_cdn_logs', year + month + day)
                },
            )
    query_id = response['QueryExecutionId']
    while 1:
        get_query = athena.get_query_execution(QueryExecutionId = query_id)
        state = get_query['QueryExecution']['Status']['State']
        if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            print ('http_code_report state: %s, completed! ' % state)
            time.sleep(3)
            break
        else:
            print ('http_code_report state: %s, waiting for completed! ' % state)
            time.sleep(3)
    return athena.get_query_results(QueryExecutionId = query_id)
# ses send mail needs to activate the recipient from console in order to prevent spam, every recipient persion needs to click confirm the email sent by aws
def send_mail(sent_content, tbl_name, region_name):
    from botocore.exceptions import ClientError
    SENDER = sender_addr
    RECIPIENT = mail_list
    SUBJECT = 'CDN %s HTTP code Statistics' % (tbl_name,)
    BODY_TEXT = sent_content
    CHARSET = 'UTF-8'
    session = boto3.Session(profile_name = profile)
    ses = session.client('ses', region_name)
    try:
        response = ses.send_email(
                Destination={
                    'ToAddresses': RECIPIENT,
                    },
                Message={
                    'Body': {
                        'Html': {
                            'Charset': CHARSET,
                            'Data': BODY_TEXT,
                            },
                        },
                    'Subject': {
                        'Charset': CHARSET,
                        'Data': SUBJECT,
                        },
                    },
                Source=SENDER,
                )
    except ClientError as e:
        print (e.response['Error']['Message'])
    else:
        print ("Email sent! Message ID: %s" % response['MessageId'])
    return response['MessageId']
def RepresentsInt(s):
    try: 
        int(s)
        return True
    except ValueError:
        return False
def http_stat(athena_db = 'gene', athena_tbl = 'test', log_bucket = 'test'):
    sent_content = '%+20s%+20s%+20s' % ('HTTP_CODE', 'NRREQUESTS', 'RATIO') + '\n'
    total_count = 0
    success_count,success_ratio = 0,0
    readline = list()
    result = http_code(tbl_name = athena_tbl, db_name = athena_db, bucket = log_bucket)
    #elements in row with empty value named None
    for row in result['ResultSet']['Rows']:
        for item in row['Data']:
            if item == {}:
                readline.append('None')
    #first row with column name ignore
            elif item['VarCharValue'] == 'HTTP_CODE':
                break
            else:
                readline.append(item['VarCharValue'])
        if len(readline) != 0:
    #change http code to integer 
    #consolidate all successful http_code < 400 to one total result
            if readline[0] != 'None'and RepresentsInt(readline[0]) and int(readline[0]) < 400:
                success_count += int(readline[1])
                success_ratio += float(readline[2])
            total_count += int(readline[1])
            #display a delightful format for float and every column with eyefideity distance
            sent_content += '%+20s%+20s%+20s' % (readline[0], readline[1], '{:.5f}'.format(float(readline[2])) + '%') + '\n' 
            readline = list()
            #add <pre> to display the computer code format in html view
    sent_content = '<pre>\n' + '######################## CDN %s statistics for %s-%s-%s ########################' % (athena_tbl, year, month, day) + '\n\n' + '%+40s' % ('Total Request Counts: ' + str(total_count)) + '\n\n' + '%+40s' % ('2XX + 3XX: ' + '{:.5f}'.format(success_ratio) + '%') + '\n\n' + sent_content + '</pre>\n'
    return sent_content
def lambda_handler(event, context):
    content = '<html>\n<body>\n'
    for cdn in cdn_lst:
#        load_partition(cdn, 'edgecast_logs', 'redacted')
        content += http_stat(athena_db, cdn, log_bucket)
    content += '</body>\n</html>\n'
    print (content)
    send_mail(content, topic, region) 


