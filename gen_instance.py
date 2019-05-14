#!/usr/bin/python3
import boto3
import os, sys
import configparser

def create ( filepath = './temp/dev.ini'):
    config = configparser.ConfigParser()
    config.optionxform = lambda option: option
    config.read(filepath)
    profile = config['env']['profile']
    disk = config._sections['disk']
    disk2 = config._sections['disk2']
    disk3 = config._sections['disk3']
    ecc = config._sections['ecc']
    net = config._sections['net']
    tag = config._sections['tag']
    iam = config._sections['iam']
    misc = config._sections['misc']

    session = boto3.session.Session(profile_name = profile)
#   ec2 = session.resource('ec2')
    iam_client = session.client('iam')
    try:
        resp = iam_client.get_instance_profile(InstanceProfileName=iam['Name'])
    except:
        iam_client.create_instance_profile(InstanceProfileName=iam['Name'])
        iam_client.add_role_to_instance_profile(InstanceProfileName=iam['Name'], RoleName=iam['Name'])

    ec2_client = session.client('ec2')
    response = ec2_client.describe_images(ImageIds=[config['ecc']['image'],])
    root_device_name = response['Images'][0]['RootDeviceName']

    if disk['snap'] != '':
        block = [
        {
            'DeviceName': disk['root'],
#instnace stored volume
#            'VirtualName': '',
            'Ebs': {
#                'Encrypted': False,
                'DeleteOnTermination': True,
#                'Iops': 0,
#                'KmsKeyId': '',
#you can restore the device from snapshot
                'SnapshotId': disk['snap'],
                'VolumeSize': int(disk['size']),
                'VolumeType': disk['type'],
            },
#some ami defined some filesystem, if you want to start as a blank device ,go for this option
#            'NoDevice': ''
        },
    ]
    else:
        block = [
        {
            'DeviceName': disk['root'],
#ephemeral driver virtual device
#            'VirtualName': '',
            'Ebs': {
#                'Encrypted': False,
                'DeleteOnTermination': True,
#                'Iops': 0,
#                'KmsKeyId': '',
#you can restore the device from snapshot
#               'SnapshotId': disk['snap'],
                'VolumeSize': int(disk['size']),
                'VolumeType': disk['type'],
            },
#some ami defined some filesystem, if you want to start as a blank device ,go for this option
#            'NoDevice': ''
        },
        {
            'DeviceName': disk2['root'],
#ephemeral driver virtual device
#            'VirtualName': '',
            'Ebs': {
#                'Encrypted': False,
                'DeleteOnTermination': True,
#                'Iops': 0,
#                'KmsKeyId': '',
#you can restore the device from snapshot
#               'SnapshotId': disk['snap'],
                'VolumeSize': int(disk2['size']),
                'VolumeType': disk2['type'],
            },
#some ami defined some filesystem, if you want to start as a blank device ,go for this option
#            'NoDevice': ''
        },
        {
            'DeviceName': '/dev/sdc',
#ephemeral driver virtual device
#            'VirtualName': '',
#            'Ebs': {
#                'Encrypted': False,
#                'DeleteOnTermination': True,
#                'Iops': 0,
#                'KmsKeyId': '',
#you can restore the device from snapshot
#               'SnapshotId': disk['snap'],
#                'VolumeSize': int(disk3['size']),
#                'VolumeType': disk3['type'],
#            },
#some ami defined some filesystem, if you want to start as a blank device ,go for this option
            'NoDevice': ''
        },
    ]


    response = ec2_client.run_instances(
    BlockDeviceMappings = block,
#you can choose the image from filter
    ImageId = ecc['image'],
    InstanceType = ecc['type'],
#   Ipv6AddressCount = 0,
#   Ipv6Addresses = [
#        {
#            'Ipv6Address': ''
#        },
#    ],
#you can use specified kernel from ami
#   KernelId = '',
#key pair is nessarary
    KeyName = ecc['key'],
    MaxCount = int(misc['mxcnt']),
    MinCount = 1,
    Monitoring = {
        'Enabled': False
    },
    Placement = {
        'AvailabilityZone': ecc['region'],
#        'Affinity': '',
#        'GroupName': '',
#        'HostId': '',
        'Tenancy': 'default',
#        'SpreadDomain': ''
    },
#   RamdiskId = '',
#   SecurityGroupIds = [
#       'sg-2c488943',
#   ],
#if you defined a vpc subunet, you only need to use sg id not sg name. 
#    SecurityGroups = [
#        'NATSG',
#    ],
#   SubnetId = 'subnet-',
    UserData = misc['udata'],
#   AdditionalInfo = '',
#   ClientToken = '',
    DisableApiTermination = False,
    DryRun = config['misc'].getboolean('dryrun'),
    EbsOptimized = False,
    IamInstanceProfile = iam,
    InstanceInitiatedShutdownBehavior = misc['tenancy'],
    NetworkInterfaces = [
        {
            'AssociatePublicIpAddress': config['net'].getboolean('public'),
            'DeleteOnTermination': True,
            'Description': tag['name'],
            'DeviceIndex': 0,
            'Groups': net['sg'].split(','),
#            'Ipv6AddressCount': 0,
#           'Ipv6Addresses': [
#               {
#                   'Ipv6Address': ''
#               },
#           ],
#            'NetworkInterfaceId': '',
#           'PrivateIpAddress': '',
            'PrivateIpAddresses': [
                {
                    'Primary': True,
                    'PrivateIpAddress': net['ip'],
                },
            ],
#           'SecondaryPrivateIpAddressCount': 0,
            'SubnetId': net['subnet'],
        },
    ],
#   PrivateIpAddress = '',
#   ElasticGpuSpecification = [
#        {
#            'Type': ''
#        },
#    ],
    TagSpecifications = [
        {
            'ResourceType': 'instance',
            'Tags': [
                        {
                            'Key': 'Name',
                            'Value': tag['name'],
                        },
                        {
                            'Key': 'server_type',
                            'Value': tag['type'],
                        },
                        {
                            'Key': 'log_label',
                            'Value': tag['log'],
                        },
                        {
                            'Key': 'environment',
                            'Value': tag['env'],
                        },
            ],
        },
        {
            'ResourceType': 'volume',
            'Tags': [
                        {
                            'Key': 'Name',
                            'Value': tag['name'],
                        },
                        {
                            'Key': 'server_type',
                            'Value': tag['type'],
                        },
                        {
                            'Key': 'log_label',
                            'Value': tag['log'],
                        },
                        {
                            'Key': 'environment',
                            'Value': 'test',
                        },
            ],
        },
		
    ],
#    LaunchTemplate = {
#        'LaunchTemplateId': '',
#        'LaunchTemplateName': '',
#        'Version': ''
#    },
#    InstanceMarketOptions = {
#        'MarketType': 'spot',
#        'SpotOptions': {
#            'MaxPrice': '',
#            'SpotInstanceType': 'persistent',
#            'BlockDurationMinutes': 0,
#            'ValidUntil': '1970-01-01T00:00:00',
#            'InstanceInterruptionBehavior': 'terminate'
#        }
#    },
#    CreditSpecification = {
#        'CpuCredits': ''
#    }
    )
    return response;
def clone( filepath='./temp/clone.ini' ):
    # create image => stop instance => run a new instance
    config = configparser.ConfigParser()
    config.optionxform = lambda option: option
    config.read(filepath)
    image_name = config['tag']['name'] 
    profile = config['env']['profile']
    instance_ids = config['clone']['instance']

    session = boto3.session.Session(profile_name = profile)
    ec2 = session.client('ec2')
    response = ec2.describe_instances(InstanceIds=[instance_ids])
    config.set('ecc', 'type', response['Reservations'][0]['Instances'][0]['InstanceType'])
#    config.set('ecc', 'key', response['Reservations'][0]['Instances'][0]['KeyName'])
    config.set('iam', 'Arn', response['Reservations'][0]['Instances'][0]['IamInstanceProfile']['Arn'])
#    config.set('net', 'sg',  response['Reservations'][0]['Instances'][0]['NetworkInterfaces'][0]['Groups'][0]['GroupId'])
    for i in range(0, len(response['Reservations'][0]['Instances'][0]['Tags'])):
        if response['Reservations'][0]['Instances'][0]['Tags'][i]['Key'] == 'Name' :
            config.set('tag', 'name', response['Reservations'][0]['Instances'][0]['Tags'][i]['Value'])
        elif response['Reservations'][0]['Instances'][0]['Tags'][i]['Key'] == 'log_label' :
            config.set('tag', 'log', response['Reservations'][0]['Instances'][0]['Tags'][i]['Value'])
        elif response['Reservations'][0]['Instances'][0]['Tags'][i]['Key'] == 'server_type' :
            config.set('tag', 'type', response['Reservations'][0]['Instances'][0]['Tags'][i]['Value'])
        elif response['Reservations'][0]['Instances'][0]['Tags'][i]['Key'] == 'enviroment' :
            config.set('tag', 'env', response['Reservations'][0]['Instances'][0]['Tags'][i]['Value'])
    with open(filepath, 'w') as temp:
        config.write(temp)
    del response


    response = ec2.describe_images(
                Filters = [{'Name':'name', 'Values':[image_name]}],
                )
    if len(response['Images']) == 0:
        rep = ec2.create_image(
            Name=image_name,
            InstanceId=instance_ids,
            NoReboot=False
            )
        image_id = rep['ImageId']
        waiter = ec2.get_waiter('image_available')
        waiter.wait(
                Filters = [{'Name':'image-id', 'Values':[image_id]}],
                ImageIds = [image_id,],
                WaiterConfig = {
                    'Delay':15,
                    'MaxAttempts':80
                    }
                )
        print (image_id,'build complete')
        del rep
    else:
        image_id = response['Images'][0]['ImageId']
    del response
    config.set('ecc', 'image', image_id)
    with open(filepath, 'w') as temp:
        config.write(temp)

#    ec2.stop_instances(InstanceIds=[instance_ids], DryRun=False, Force=False)
#    waiter = ec2.get_waiter('instance_stopped')
#    filter = [{'Name':'instance-id', 'Values':[instance_ids]}]
#    waiter.wait(Filters = filter,DryRun = False)
    response = create(filepath)
    return response;
if __name__ == '__main__':
    if len(sys.argv) < 3:
        print ('Usage: ',sys.argv[0],'create/clone temp/conf_file.ini')
        sys.exit(2)
    filepath = './temp/'+sys.argv[2]+'.ini'
    if os.path.exists(filepath):
        print (getattr(sys.modules[__name__], sys.argv[1])(filepath))
    else:
        print ('config file do not exists, quit!')
        sys.exit(2)
