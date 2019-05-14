#!/usr/bin/python3
import boto3
import datetime
from botocore.exceptions import ClientError
import time 
import sys, os
import json
import re
#ssm_parameter,env,document_name,
# string in dictionary is the correct one, string must nest with quote/double quote
# no need to wait the ssm automation finish, i use the document to trigger asg_tweak lambda function
def lambda_handler(event, context):
    date_str = datetime.date.today().strftime('%Y%m%d')
    time_str = datetime.datetime.now().strftime('%H%M')
    env = os.environ.get('ENVIRONMENT', None)
    if env == None:
        env = 'dev'
    parameterName = os.environ.get('PARAMETER', None)
    if parameterName == None:
        parameterName = 'LatestAmi'
    doc_name = os.environ.get('DOCNAME', None)
    conf = conf_handling('r')
    try:
        session = boto3.Session()
        ssm_client = session.client('ssm')
        #parameterName = LatestAmi
        resp = ssm_client.get_parameter(
            Name = parameterName
            )
        if 'Parameter' in resp:
            if 'Value' in resp['Parameter']:
                src_ami = resp['Parameter']['Value']
            else:
                return 'no ssm parameter value'
        else:
            return 'no ssm parameter'
        resp = ssm_client.list_documents(
                DocumentFilterList=[
                    {
                        'key': 'Name',
                        'value': doc_name 
                        },
                    ],
                )
        doc_name = resp['DocumentIdentifiers'][0]['Name']
        resp = ssm_client.start_automation_execution(
            DocumentName = doc_name,
            Parameters = {
            'SourceAmiId': [
                src_ami,
                ],
            'SubnetId': [
                conf[env]['subnet'],
                ],
            'TargetAmiName': [
                'base-app-{2}-{0}-{1}'.format(date_str,time_str,env),
                ],
            },
        )
    except ClientError as e:
        print (e)
    return resp
def ssm_waiter(exec_id):
    try:
        session = boto3.Session(profile_name = profile)
        ssm_client = session.client('ssm')
        while 1:
            resp = ssm_client.describe_automation_executions(
                    Filters=[
                        {
                            'Key': 'ExecutionId',
                            'Values': [
                                exec_id,
                                ]
                            },
                        ],
                    )
            if 'AutomationExecutionMetadataList' in resp:
                if resp['AutomationExecutionMetadataList'][0]['AutomationExecutionStatus'] in ['Success', 'TimeOut', 'Cancelled', 'Failed']:
                    print ('exec_id {1} status {0}'.format(resp['AutomationExecutionMetadataList'][0]['AutomationExecutionStatus'], exec_id))
                    target_ami = resp['AutomationExecutionMetadataList'][0]['Outputs']['createImage.ImageId'][0]
                    break
                else:
                    print ('in progress, please waiting for complete')
                    time.sleep(30)
    except ClientError as e:
        print ('unexpected error: {0}'.format(e))
    return target_ami
def conf_handling(mode = 'r', conf_dict = None):
    if mode == 'r':
        with open('config.json', 'r') as jf:
            conf = json.load(jf)
        jf.close()
        return conf
    elif mode == 'w' and conf_dict != None:
        with open('config.json', 'w') as jf:
            json.dump(conf_dict, jf)
        jf.close()
        print ("configuration saved!")
    else:
        print ("unexpected error!")
        sys.exit(-1)
