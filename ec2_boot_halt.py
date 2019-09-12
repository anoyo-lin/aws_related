#!/usr/bin/python3
import boto3
import datetime
import time
import json
import sys, os

def lambda_handler(event=None, context=None):
    print (json.dumps(event, indent=2))
    profile = None

    env = os.environ.get('ENVIRONMENT', None)
    if env == None:
        env = 'dev'
    threshold = int(os.environ.get('THRESHOLD', 0))
    if threshold == 0:
        threshold = 300
    region_name = os.environ.get('REGION_NAME', None)
    if region_name == None:
        region_name = 'us-east-1'
    instance_lst = os.environ.get('EC2_LST', None)
    if instance_lst == None:
        instance_lst = 'i-09ae543f88ffc590f,i-09ae543f88ffc590f'
    instance_lst = instance_lst.split(',')

    try:
        session = boto3.Session(profile_name = profile)
        ec2_client = session.client('ec2', region_name = region_name)
        resp = ec2_client.describe_instances(
                InstanceIds = instance_lst
                )
        for instance in resp['Reservations'][0]['Instances']:
            if instance['State']['Name'] == 'running':
                start = datetime.datetime.now()
                stop_resp = ec2_client.stop_instances(
                        InstanceIds=[
                            instance['InstanceId'],
                            ],
                        )
                while 1:
                    status_check = ec2_client.describe_instances(
                            InstanceIds = [
                                instance['InstanceId'],
                                ],
                            )
                    try:
                        if status_check['Reservations'][0]['Instances'][0]['State']['Name'] == 'stopped':
                            break
                        else:
                            stop = datetime.datetime.now()
                            if round((stop-start).total_seconds())//threshold >= 1:
                                print ('exceed the threshold {0} seconds, time out and exit'.format(threshold))
                                sys.exit(-1)
                            print ('waiting the {0} to stop, 60 seconds'.format(instance['InstanceId']))
                            time.sleep(60)
                    except Exception as e:
                        print ('Error: %s' % (e,))


            elif instance['State']['Name'] == 'stopped':
                start = datetime.datetime.now()
                start_resp = ec2_client.start_instances(
                        InstanceIds=[
                            instance['InstanceId'],
                            ],
                        )
                while 1:
                    status_check = ec2_client.describe_instances(
                            InstanceIds = [
                                instance['InstanceId'],
                                ],
                            )
                    try:
                        if status_check['Reservations'][0]['Instances'][0]['State']['Name'] == 'running':
                            break
                        else:
                            stop = datetime.datetime.now()
                            if round((stop-start).total_seconds())//threshold >= 1:
                                print ('exceed the threshold {0} seconds, time out and exit'.format(threshold))
                                sys.exit(-1)
                            print ('waiting the {0} to start, 60 seconds'.format(instance['InstanceId']))
                            time.sleep(60)
                    except Exception as e:
                        print ('Error: %s' % (e,))
    except Exception as e:
        print ('Error: %s' % (e,))

if __name__ == '__main__':
    lambda_handler()

