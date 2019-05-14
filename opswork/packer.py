#!/usr/bin/python3
import boto3
import os, sys
import re
import configparser

if len(sys.argv) != 2:
    print (sys.argv[0] dev/stage/produs/prodeu)
    sys.exit(-1)
filepath = './temp/{0}.ini'.format(sys.argv[1])

ec2 = ec2_init(filepath, 'resource', 'ec2')
ec2_asg = ec2_init(filepath, 'client', 'autoscaling')
ec2_ssm = ec2_init(filepath, 'client', 'ssm')

def ec2_init(filepath = './temp/dev.ini', method = 'resource', module = 'ec2'):
    config = configparser.ConfigParser()
    config.read(filepath)
    profile = config['env']['profile']
    global owner
    owner = config['env']['owner']
    session = boto3.Session(profile_name = profile)
    if method == 'resource':
        ec2_res = session.resource(module)
        return ec2_res
    else:
        ec2_client = session.client(module)
        return ec2_client


def asg_lc_ami():
    response = ec2_asg.describe_auto_scaling_groups()
    systest_lc = list()
    test_lc = list()
    pattern = re.compile('.*systest$')
    for asg_lc_name in response['AutoScalingGroups']:
        if asg_lc_name['AutoScalingGroupName'] not in systest_lc and pattern.search(asg_lc_name['AutoScalingGroupName']):
            systest_lc.append(asg_lc_name['LaunchConfigurationName'])
        elif asg_lc_name['AutoScalingGroupName'] not in systest_lc and not pattern.search(asg_lc_name['AutoScalingGroupName']):
            test_lc.append(asg_lc_name['LaunchConfigurationName'])

    response = ec2_asg.describe_launch_configurations(LaunchConfigurationNames = systest_lc)
    systest_ami = set()
    for asg_lc_ami in response['LaunchConfigurations']:
        systest_ami.add(ec2.Image(asg_lc_ami['ImageId']))
    response = ec2_asg.describe_launch_configurations(LaunchConfigurationNames = test_lc)
    test_ami = set()
    for asg_lc_ami in response['LaunchConfigurations']:
        test_ami.add(ec2.Image(asg_lc_ami['ImageId']))
    return systest_ami,test_ami

def waiter (ExecutionId):
    while 1:
        response = ec2_ssm.describe_automation_executions(
            Filters = [
                {
                    'Key': 'ExecutionId',
                    'Values': [
                        ExecutionId,
                        ]
                    },
                ],
            )
        if len(response['AutomationExecutionMetadataList']) != 0:
            if response['AutomationExecutionMetadataList'][0]['AutomationExecutionStatus'] == 'Success':
                print ('{0} execution complete'.format(ExecutionId))
                break 
            elif response['AutomationExecutionMetadataList'][0]['AutomationExecutionStatus'] == 'Failed':
                print ('{0} execution failed'.format(ExecutionId))
                sys.exit(-1)
            else:
                print ('{0} in progress, wait 5 seonds to refresh status'.format(ExecutionId))
                sys.sleep(5)
        else:
            print ('no record found, exit')
            sys.exit(-1)





if __name__ == '__main__':
    print (asg_lc_ami('./temp/dev.ini'))
