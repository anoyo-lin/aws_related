#!/usr/bin/python3
import boto3
import datetime
from botocore.exceptions import ClientError
import time 
import sys, os
import json
import re
#ssm_parameter,env
#paramater need to define in every function if you dont publice annoucement
#i can't figure out how ssm can set filter with user-define tags as filter(may be it can write as 'Key': 'tag:LogicName'
#so i change to DocumentFilterList as the practice one.
#but this one can only change the current LC profile, it can not refresh the instance running now, so i assume we can use lambda to change it from beginning 
# at this script once that was done, sending a notification to AWS SQS/SNS, then trigger a lambda to revert it back to normal


def lambda_handler(event, context):
    print (json.dumps(event, indent=2))
    session = boto3.Session()
    ssm_client = session.client('ssm')
    resp = ssm_client.describe_parameters(
            Filters=[
                {
                    'Key': 'Name',
                    'Values': [ event['parameterName'] ]
                    },
                ]
            )
    if not resp['Parameters']:
        print ('No such parameter')
        return 'SSM parameter not found.'
    if 'Description' in resp['Parameters'][0]:
        description = resp['Parameters'][0]['Description']
        resp = ssm_client.put_parameter(
                Name = event['parameterName'],
                Value = event['parameterValue'],
                Description = description,
                Type = 'String',
                Overwrite = True
                )
    else:
        resp = ssm_client.put_parameter(
                Name = event['parameterName'],
                Value = event['parameterValue'],
                Type = 'String',
                Overwrite = True
                )
    profile = None
    env = os.environ.get('ENVIRONMENT', None)
    if env == None:
        env = 'dev'
    conf = conf_handling('r')
    region = conf[env]['region']
    asg_names = conf[env]['asg_names']
    target_ami = event['parameterValue']

    interval = 300//len(asg_names) - 10

    push = re.compile('.*push$')
    sys_push = re.compile('.*push-systest$')
    sender = re.compile('.*sender.*')
    receiver = re.compile('.*receiver.*')

    for asg_name in asg_names:
        if push.search(asg_name):
            lc_name = create_lc(target_ami, conf[env]['push']['instance_type'], conf[env]['push']['sg'], 'push')
            asg_tweak(asg_name, lc_name, conf[env]['push']['asg_renew']['minimum'], conf[env]['push']['asg_renew']['maximum'], conf[env]['push']['asg_renew']['desired'])
            time.sleep(interval)
            asg_tweak(asg_name, lc_name, conf[env]['push']['asg_origin']['minimum'], conf[env]['push']['asg_origin']['maximum'], conf[env]['push']['asg_origin']['desired'])
        if sys_push.search(asg_name):
            lc_name = create_lc(target_ami, conf[env]['push']['instance_type'], conf[env]['push']['sg'], 'sys_push')
            asg_tweak(asg_name, lc_name, conf[env]['push']['asg_renew']['minimum'], conf[env]['push']['asg_renew']['maximum'], conf[env]['push']['asg_renew']['desired'])
            time.sleep(interval)
            asg_tweak(asg_name, lc_name, conf[env]['push']['asg_origin']['minimum'], conf[env]['push']['asg_origin']['maximum'], conf[env]['push']['asg_origin']['desired'])
        elif sender.search(asg_name):
            lc_name = create_lc(target_ami, conf[env]['sender']['instance_type'], conf[env]['sender']['sg'], 'sender')
            asg_tweak(asg_name, lc_name, conf[env]['sender']['asg_renew']['minimum'], conf[env]['sender']['asg_renew']['maximum'], conf[env]['sender']['asg_renew']['desired'])
            time.sleep(interval)
            asg_tweak(asg_name, lc_name, conf[env]['sender']['asg_origin']['minimum'], conf[env]['sender']['asg_origin']['maximum'], conf[env]['sender']['asg_origin']['desired'])
        elif receiver.search(asg_name):
            lc_name = create_lc(target_ami, conf[env]['receiver']['instance_type'], conf[env]['receiver']['sg'], 'receiver')
            asg_tweak(asg_name, lc_name, conf[env]['receiver']['asg_renew']['minimum'], conf[env]['receiver']['asg_renew']['maximum'], conf[env]['receiver']['asg_renew']['desired'])
            time.sleep(interval)
            asg_tweak(asg_name, lc_name, conf[env]['receiver']['asg_origin']['minimum'], conf[env]['receiver']['asg_origin']['maximum'], conf[env]['receiver']['asg_origin']['desired'])
    
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

def create_lc(target_ami, instance_type, instance_sg, lc_name):
    profile = None
    env = os.environ.get('ENVIRONMENT', None)
    if env == None:
        env = 'dev'
    conf = conf_handling('r')
    date_str = datetime.date.today().strftime('%Y%m%d')
    time_str = datetime.datetime.now().strftime('%H%M')
    import base64
    with open('./userdata.txt', 'rb') as stream:
#        user_data = base64.b64encode(stream.read())
        user_data = stream.read()

    try:
        session = boto3.Session(profile_name = profile)
        asg_client = session.client('autoscaling')
    

        resp = asg_client.create_launch_configuration(
        LaunchConfigurationName='{2}-lc-{0}-{1}'.format(date_str,time_str,lc_name),
        ImageId=target_ami,
        KeyName=conf[env]['instance_key'],
        SecurityGroups=instance_sg,
        UserData=user_data,
        InstanceType=instance_type,
        BlockDeviceMappings=conf[env]['disk_info'],
        InstanceMonitoring={
            'Enabled': False
        },
        IamInstanceProfile=conf[env]['iam_profile'],
        EbsOptimized=False,
        AssociatePublicIpAddress=True,
        )
    except ClientError as e:
        print ('unexpect error: {0}'.format(e))
    return '{2}-lc-{0}-{1}'.format(date_str,time_str,lc_name) 

def asg_waiter(asg_name, target_desired):
    profile = None
    while 1:
        try:
            session = boto3.Session(profile_name = profile)
            asg_client = session.client('autoscaling')
            resp = asg_client.describe_auto_scaling_groups(
                AutoScalingGroupNames=[
                asg_name,
                ],
                )
        except ClientError as e:
            print ('Unexpect Error {0}'.format(e))
        counter = 0 
        if 'AutoScalingGroups' in resp:
            for asg in resp['AutoScalingGroups']:
                if len(asg['Instances']) != target_desired:
                    counter += 1
                for instance in asg['Instances']:
                    if instance['LifecycleState'] != 'InService':
                        counter += 1
        if counter == 0:
            print ('asg_change_complete!')
            break
        else:
            print ('executing, please wait another 20 secs')
            time.sleep(20)

#https://stackoverflow.com/questions/42399072/aws-update-autoscaling-group-with-new-ami-automatically
def asg_tweak(asg_name, lc_name, min_cnt, max_cnt, desired ):
    profile = None
    try:
        session = boto3.Session(profile_name = profile)
        asg_client = session.client('autoscaling')
    

        resp = asg_client.update_auto_scaling_group(
        AutoScalingGroupName=asg_name,
        LaunchConfigurationName=lc_name,
#    LaunchTemplate={
#        'LaunchTemplateId': 'string',
#        'LaunchTemplateName': 'string',
#        'Version': 'string'
#    },
#    MixedInstancesPolicy={
#        'LaunchTemplate': {
#            'LaunchTemplateSpecification': {
#                'LaunchTemplateId': 'string',
#                'LaunchTemplateName': 'string',
#                'Version': 'string'
#            },
#            'Overrides': [
#                {
#                    'InstanceType': 'string'
#                },
#            ]
#        },
#        'InstancesDistribution': {
#            'OnDemandAllocationStrategy': 'string',
#            'OnDemandBaseCapacity': 123,
#            'OnDemandPercentageAboveBaseCapacity': 123,
#            'SpotAllocationStrategy': 'string',
#            'SpotInstancePools': 123,
#            'SpotMaxPrice': 'string'
#        }
#    },
        MinSize=min_cnt,
        MaxSize=max_cnt,
        DesiredCapacity=desired,
#    DefaultCooldown=300,
#    AvailabilityZones=[
#        'us-east-1b',
#    ],
#    HealthCheckType='EC2',
#    HealthCheckGracePeriod=300,
#    PlacementGroup='string',
#    VPCZoneIdentifier='subnet-215e174d',
        TerminationPolicies=[
            'OldestLaunchConfiguration',
        ],
#    NewInstancesProtectedFromScaleIn=False,
#    ServiceLinkedRoleARN='ServiceLinkedRoleARN": "arn:aws:iam::251599223714:role/aws-service-role/autoscaling.amazonaws.com/AWSServiceRoleForAutoScaling'
        )
    except ClientError as e:
        print ( 'unexpect error: {0}.'.format(e))
#    asg_waiter(asg_name, desired)
