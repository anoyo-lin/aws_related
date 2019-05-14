#!/usr/bin/python3
import boto3
import re
from operator import itemgetter
from beautifultable import BeautifulTable
from prettytable import PrettyTable
import os, sys
import configparser
def extract_tags(lst=[],name='Name'):
    for i in range(0, len(lst)):
            if lst[i]['Key'] == name:
                return lst[i]['Value']
    return None
def disp_vol(filepath='./temp/dev/ini'):
    config = configparser.ConfigParser()
    config.read(filepath)
    profile = config['env']['profile']
    table = BeautifulTable()
    table.column_headers = ['id', 'type', 'state', 'size', 'iops', 'az', 'attach', 'instance', 'kms', 'snap', 'create']

    session = boto3.session.Session(profile_name=profile)
    ec2 = session.resource('ec2')
    ec2_client = session.client('ec2')
    for volume in ec2.volumes.all():
        if len(volume.attachments) != 0:
            instance = ec2.Instance(volume.attachments[0]['InstanceId'])
            tags = extract_tags(instance.tags, 'Name')
            device = volume.attachments[0]['Device']
        else:
            tags = 'N/A'
            device = 'N/A'
        snapshot = ec2_client.describe_snapshots(Filters = [ { 'Name': 'volume-id', 'Values': [volume.id, ] }, ], )
        if len(snapshot['Snapshots']) == 0:
            table.append_row([volume.id, volume.volume_type, volume.state, volume.size, volume.iops, volume.availability_zone, device, tags, volume.kms_key_id, 'N/A', 'N/A'])
        else:

            for i in range(0,len(snapshot['Snapshots'])):
                snapshot_id = snapshot['Snapshots'][i]['SnapshotId']
                snapshot_time = snapshot['Snapshots'][i]['StartTime'].strftime("%Y%m%d%H%M%S")
                if i == 0:
                    table.append_row([volume.id, volume.volume_type, volume.state, volume.size, volume.iops, volume.availability_zone, device, tags, volume.kms_key_id, snapshot_id, snapshot_time])
                else:
                    table.append_row(['', '', '', '', '', '', '', '', '', snapshot_id, snapshot_time])


        
    print (table)
    return; 


def ls_img(filepath='./temp/dev.ini'):
    config = configparser.ConfigParser()
    config.read(filepath)
    profile = config['env']['profile']
    owner = config['image']['owner']
    name = config ['image']['name']
    arch = config['image']['arch']
    vtype = config['image']['vtype']
    itype = config['image']['itype']


    table = BeautifulTable(max_width=160)
#    table.width_exceed_policy = BeautifulTable.WEP_ELLIPSIS
    table.column_headers = ['name', 'enaSupport', 'Id', 'SriovNet', 'type', 'deviceType', 'arch', 'root']

    session = boto3.session.Session(profile_name=profile)
    ec2_client = session.client('ec2') 
    resp = ec2_client.describe_images(
        Owners = [owner],
        Filters=[
            {
                'Name': 'architecture',
                'Values': [
                    arch,
                ]
            },
            {
                'Name': 'owner-alias',
                'Values': [
                    owner,
                ]
            },
            {
                'Name': 'image-type',
                'Values': [
                    itype,
                ]
            },
            {
                'Name': 'virtualization-type',
                'Values': [
                    vtype,
                ]
            },
        ],

        )
    re_name = re.compile(name)
    image_id = sorted(
        [ item for item in resp['Images'] if item.get('Name', None) and re_name.search(item['Name']) ]
            ,key=itemgetter(u'CreationDate'))
    for i in range(0,len(image_id)):
        if 'RootDeviceName' in image_id[i]:
            root = image_id[i]['RootDeviceName']
        else:
            root = 'N/A'
        if 'EnaSupport' in image_id[i]:
            ena = image_id[i]['EnaSupport']
        else:
            ena = 'N/A'
        if 'SriovNetSupport' in image_id[i]:
            sriov = image_id[i]['SriovNetSupport']
        else:
            sriov = 'N/A'

        #if 'EnaSupport' in image_id[i] and 'SriovNetSupport' in image_id[i] and 'RootDeviceName' in image_id[i]:
            #table.append_row([image_id[i]['Name'],image_id[i]['EnaSupport'],image_id[i]['ImageId'],image_id[i]['SriovNetSupport'],image_id[i]['VirtualizationType'],image_id[i]['RootDeviceType'],image_id[i]['Architecture'], image_id[i]['RootDeviceName']])
        #elif 'SriovNetSupport' in image_id[i] and 'RootDeviceName' in image_id[i]:
            #table.append_row([image_id[i]['Name'],'N/A',image_id[i]['ImageId'],image_id[i]['SriovNetSupport'],image_id[i]['VirtualizationType'],image_id[i]['RootDeviceType'],image_id[i]['Architecture'], image_id[i]['RootDeviceName']])
        #elif 'RoootDeviceName' in image_id[i]:
            #table.append_row([image_id[i]['Name'],'N/A',image_id[i]['ImageId'],'N/A',image_id[i]['VirtualizationType'],image_id[i]['RootDeviceType'],image_id[i]['Architecture'], image_id[i]['RootDeviceName']])
        #else:
        table.append_row([image_id[i]['Name'],ena,image_id[i]['ImageId'],sriov,image_id[i]['VirtualizationType'],image_id[i]['RootDeviceType'],image_id[i]['Architecture'], root])
    print (table)
    return image_id[-1]['ImageId']


def info(filepath = './temp/dev.ini'):
#    table = BeautifulTable()
#    table.default_alignment = BeautifulTable.ALIGN_CENTER
#    table.width_exceed_policy = BeautifulTable.WEP_STRIP
#    table.column_widths = [ 100, 20, 20, 20, 20, 20, 20, 20, 10, 10 ]
    table = PrettyTable(['name', 'id', 'state', 'key', 'iam', 'az', 'type', 'dev', 'volume', 'size', 'vtype'])
    table.padding_width = 0
    config = configparser.ConfigParser()
    config.read(filepath)

    session = boto3.session.Session(profile_name=config['env']['profile'])
    ec2 = session.resource('ec2')
    for instance in ec2.instances.all():
        if len(instance.block_device_mappings) > 0:
            for i in range(0, len(instance.block_device_mappings)):
#                for j in range(0, len(instance.tags)):
#                    if instance.tags[j]['Key'] == 'Name':
#                        for k in range(0, len(instance.network_interfaces_attribute)):
#                            if instance.network_interfaces_attribute[k]['PrivateIpAddresses']:
#                                for l in range(0, len(instance.network_interfaces_attribute[k]['PrivateIpAddresses'])):
#                                    if instance.network_interfaces_attribute[k]['PrivateIpAddresses'][l]['PrivateDnsName']:
#                                        table.append_row([instance.tags[j]['Value'], instance.id, instance.state['Name'], instance.key_name, instance.instance_type, instance.block_device_mappings[i]['DeviceName'], instance.block_device_mappings[i]['Ebs']['VolumeId'], instance.network_interfaces_attribute[k]['PrivateIpAddresses'][l]['PrivateDnsName']])
                if i==0:
                     for j in range(0, len(instance.tags)):
                         if instance.tags[j]['Key'] == 'Name':
                             iam = instance.iam_instance_profile['Arn'] if instance.iam_instance_profile != None else 'N/A'
                             table.add_row([instance.tags[j]['Value'], instance.id, instance.state['Name'], instance.key_name, iam, instance.placement['AvailabilityZone'], instance.instance_type, instance.block_device_mappings[i]['DeviceName'], instance.block_device_mappings[i]['Ebs']['VolumeId'], ec2.Volume(instance.block_device_mappings[i]['Ebs']['VolumeId']).size, instance.virtualization_type])

                else:
                        table.add_row(['','','','','','','', instance.block_device_mappings[i]['DeviceName'], instance.block_device_mappings[i]['Ebs']['VolumeId'], ec2.Volume(instance.block_device_mappings[i]['Ebs']['VolumeId']).size, ''])
        elif instance.tags!= None:
            for j in range(0, len(instance.tags)):
                if instance.tags[j]['Key'] == 'Name':
                    iam = instance.iam_instance_profile['Arn'] if instance.iam_instance_profile != None else 'N/A'
                    table.add_row([instance.tags[j]['Value'], instance.id, instance.state['Name'], instance.key_name, iam, instance.placement['AvailabilityZone'], instance.instance_type, 'N/A', 'N/A', 'N/A', instance.virtualization_type])
    print (table)
    del table
#    table = BeautifulTable(max_width=170)
    #table.width_exceed_policy = BeautifulTable.WEP_ELLIPSIS
    table = PrettyTable(['name', 'id', 'state', 'private', 'public', 'subnet', 'vpc', 'group', 'net-id', 'ena', 'sriov'])
    table.padding_width = 0
    for instance in ec2.instances.all():
        if instance.tags != None:
            for j in range(0, len(instance.tags)):
                if instance.tags[j]['Key'] == 'Name':
                    if len(instance.network_interfaces_attribute) > 0:
                        if 'Association' in instance.network_interfaces_attribute[0]['PrivateIpAddresses'][0]:
                            table.add_row([instance.tags[j]['Value'], instance.id, instance.state['Name'], instance.network_interfaces_attribute[0]['PrivateIpAddress'], instance.network_interfaces_attribute[0]['PrivateIpAddresses'][0]['Association']['PublicIp'], instance.network_interfaces_attribute[0]['SubnetId'], instance.network_interfaces_attribute[0]['VpcId'], instance.network_interfaces_attribute[0]['Groups'], instance.network_interfaces_attribute[0]['NetworkInterfaceId'], instance.ena_support, instance.sriov_net_support])
                        else:
                            table.add_row([instance.tags[j]['Value'], instance.id, instance.state['Name'], instance.network_interfaces_attribute[0]['PrivateIpAddress'], 'N/A', instance.network_interfaces_attribute[0]['SubnetId'], instance.network_interfaces_attribute[0]['VpcId'], instance.network_interfaces_attribute[0]['Groups'], instance.network_interfaces_attribute[0]['NetworkInterfaceId'], instance.ena_support, instance.sriov_net_support])
    print (table)
    return;

#def new(   profile='dev', 
#    disk={'root':'/dev/xvda', 'size':8, 'type':'gp2', 'snap':''}, 
#    ecc={'image':'ami-', 'type':'t2.micro', 'key':'redacted', 'region':'us-east-1b'},
#    net={'sg':'redacted', 'subnet':'redacted'},
#    tag={'name':'MicroNAT', 'type':'uep-support', 'log':'nolog', 'env':'test'},
#    stop_after = 5         ):

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print (sys.argv[0],'info/ls_img temp/config_file.ini')
        sys.exit(2)
#    try:
#        opts, args = getopt.getopt(sys.argv[2:], 'hf:', ['filepath='])
#    except getopt.GetoptError as err:
#        print (sys.argv[0:2],'-f filepath')
#        sys.exit(2)
#    for opt, arg in opts:
#        if opt == '-h':
#            print (sys.argv[0:2],'-f filepath')
#            sys.exit()
#        elif opt in ('-f', '--filepath'):
#            filepath = arg
    filepath='./temp/' + sys.argv[2] + '.ini'
    if os.path.exists(filepath):
        getattr(sys.modules[__name__], sys.argv[1])(filepath)
    else:
        print ('config file do not exists, quit!')
        sys.exit(2)

#info(profile='dev')
#image_id = latest_image(profile='dev',owner=['amazon'], name='amzn.*ebs') 
#response = new(   profile='dev',
#        disk={'root':'/dev/xvda', 'size':8, 'type':'standard', 'snap':''},
#        ecc={'image':image_id, 'type':'t2.micro', 'key':'redacted', 'region':'us-east-1b'},
#        net={'sg':'redacted', 'subnet':'redacted'},
#        tag={'name':'gene', 'type':'uep-support', 'log':'nolog', 'env':'test'}
#                    )
#print (response)
