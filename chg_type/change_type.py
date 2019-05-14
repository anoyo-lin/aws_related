#!/usr/bin/python3
import boto3
import sys, getopt
from botocore.exceptions import ClientError
def change_type(profile,instance_ids,instance_type):
    try:
        session = boto3.session.Session(profile_name=profile)
        ec2 = session.client('ec2')
        filters = [{'Name':'instance-id', 'Values':[instance_ids]}]
        rep_stop = ec2.stop_instances(InstanceIds=[instance_ids], DryRun=False, Force=False)
        waiter = ec2.get_waiter('instance_stopped')
        waiter.wait(Filters = filters,DryRun = False)
        print (rep_stop)
        ec2.modify_instance_attribute(InstanceId=instance_ids, InstanceType={'Value':instance_type})
        ec2.modify_instance_attribute(InstanceId=instance_ids, EnaSupport={'Value':True})
        rep_start = ec2.start_instances(InstanceIds=[instance_ids], DryRun=False)
        waiter2 = ec2.get_waiter('instance_running')
        waiter2.wait(Filters = filters,DryRun = False)
        print (rep_start)
    except ClientError as err:
        if err.response['Error']['Code'] == 'EntityAlreadyExists':
            print ('user already exists')
            sys.exit(1)
        else:
            print ('Unexpected error: %s' % err)
            sys.exit(1)

    return;
#change_type('dev','i-036734376f2de1098','t2.micro')
if __name__ == '__main__':
    if len(sys.argv) < 4:
        print ("usage: ", sys.argv[0], '--env=dev --id=i-123456 --type=t2.micro')
        sys.exit(2)
    try:
        opts,args = getopt.getopt(sys.argv[1:], '', ['env=', 'id=', 'type='])
    except getopt.GetoptError as err:
        print (err)
        print ("usage: ", sys.argv[0], '--env=dev --id=i-123456 --type=t2.micro')
        sys.exit(2)
    for opt, argv in opts:
        if opt == '--env':
            profile = argv
        elif opt == '--id':
            instance_ids = argv
        elif opt == '--type':
            instance_type = argv
    change_type(profile, instance_ids, instance_type)
