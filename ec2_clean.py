#!/usr/bin/python3
import boto3
import configparser
from datetime import datetime, tzinfo, timedelta
import re
import sys, os
import time
""" abc concept, self can gather self attribution in function
global parameter
for will assign naked generator object to a list/set/dict,
but we can get the object by list() so you can see list( i for i in object)[0] in code
it will get objects by for-loop, if you feel convenient to debug
make no mistake about the return type (string or object)?
bubble sort for i in len(list)(for j in len(list)-1-i)
asg => lc => ami => snapshot
ami => lc => asg => elb => route 53

"""

class tz(tzinfo):
    def __init__(self, offset, isdst, name):
        self.offset = offset
        self.isdst = isdst
        self.name = name
    def utcoffset(self, dt):
        return timedelta(hours=self.offset) + self.dst(dt)
    def dst(self, dt):
        return timedelta(hours=1) if self.isdst else timedelta(0)
    def tzname(self,dt):
        return self.name

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

def unused_ami_exempt(filepath = './temp/dev.ini', keyword = 'base-app-test-', reserved_counter = 2):
    ec2 = ec2_init(filepath, 'resource', 'ec2')
    regex = keyword + '(.*)'
    reserved_counter = 0 - reserved_counter
    used_images = list(instance.image_id for instance in ec2.instances.all())
    used_images = set(image for image in ec2.images.filter(ImageIds=used_images))
    unused_images = set(image for image in ec2.images.filter(Owners=[owner,]) if image not in used_images)

    time_cols = list() 
#    latest = datetime(1970,1,1,0,0,0,0) 
#    for used_image in used_images:
#        i = list(image for image in ec2.images.filter(ImageIds=[used_image]))
#        if len(i) != 0:
#            print (i[0].name)
#        else:
#            print ('N/A')
    
    for unused_image in unused_images:
        ami_time = re.match(r'%s' % regex, unused_image.name)
        if ami_time and datetime.strptime(ami_time.groups()[0], "%Y%m%d-%H%M") not in time_cols:
            time_cols.append(datetime.strptime(ami_time.groups()[0], "%Y%m%d-%H%M"))
    if len(time_cols) > 2:
        for index in range(0, len(time_cols)):
            for bubble_index in range(0, len(time_cols) - index - 1):
                if time_cols[bubble_index] > time_cols[bubble_index + 1]:
                    temp = time_cols[bubble_index]
                    time_cols[bubble_index] = time_cols[bubble_index + 1]
                    time_cols[bubble_index + 1] = temp
    undel = set()
    for undel_old in time_cols[reserved_counter:]:
        undel_desc = keyword + datetime.strftime(undel_old, "%Y%m%d-%H%M")
        undel.add([ image for image in ec2.images.filter(Filters = [{'Name':'name', 'Values':[undel_desc]}], Owners = [owner]) ][0])
#        for image in ec2.images.filter(Filters = [{'Name':'name', 'Values':[undel_desc]}], Owners = [owner]):
#            temp = image
#        undel.add(temp)
        
    return undel

def asg_lc_ami(filepath = './temp/dev.ini'):
    ec2_asg = ec2_init(filepath, 'client', 'autoscaling')
    ec2 = ec2_init(filepath, 'resource', 'ec2')
    response = ec2_asg.describe_auto_scaling_groups()
    reserved_lc = list()
    for asg_lc_name in response['AutoScalingGroups']:
        if asg_lc_name not in reserved_lc:
            reserved_lc.append(asg_lc_name['LaunchConfigurationName'])
    response = ec2_asg.describe_launch_configurations(LaunchConfigurationNames = reserved_lc)
    reserved_ami = set() 
    for asg_lc_ami in response['LaunchConfigurations']:
        reserved_ami.add(ec2.Image(asg_lc_ami['ImageId']))
    return reserved_ami

#whitelist = unused_ami_exempt + asg_lc_ami, delete the ami's snapshot without owner
def clean_ami(filepath = './temp/dev.ini', retention = 7):
    if filepath == './temp/dev.ini':
        prefix_1 = 'base-app-systest-'
        prefix_2 = 'base-app-test-'
    elif filepath == './temp/stage.ini':
        prefix_1 = 'base-app-stage-'
    elif filepath == './temp/produs.ini':
        prefix_1 = 'base-app-produs-'
    elif filepath == './temp/prodeu.ini':
        prefix_1 = 'base-app-prodeu-'
    CST = tz(8, False, 'UTC+8')
    retention = datetime.now() - timedelta(days = retention)
    ec2 = ec2_init(filepath, 'resource', 'ec2')
    used_images = list(instance.image_id for instance in ec2.instances.all())
    used_images = set(image for image in ec2.images.filter(ImageIds=used_images))
    unused_images = set(image for image in ec2.images.filter(Owners=[owner,]) if image not in used_images)
    if filepath == './temp/dev.ini':
        whitelist = unused_ami_exempt(filepath, prefix_1, 1) | unused_ami_exempt(filepath, prefix_2, 1) | asg_lc_ami(filepath) - used_images
    else:
        whitelist = unused_ami_exempt(filepath, prefix_1, 1) | asg_lc_ami(filepath) - used_images
    for image in unused_images:
        if datetime.strptime(image.creation_date, "%Y-%m-%dT%H:%M:%S.000Z") < retention and image not in whitelist:
            print (image.deregister(DryRun=False))
            time.sleep(3)
    return 'deregister unwanted ami'

def clean_ss(filepath = './temp/dev.ini'):
    ec2 = ec2_init(filepath, 'resource', 'ec2')
    images = []
    for image in ec2.images.filter(Owners=[owner]):
        images.append(image.id)
    for snapshot in ec2.snapshots.filter(OwnerIds=[owner]):
        ami_name = re.match(r".*for (ami-.*) from.*", snapshot.description)
        if ami_name:
            if ami_name.groups()[0] not in images:
                print(snapshot.delete(DryRun=False))
                time.sleep(1)
    return 'delete no related host snapshot'

def clean_lc(filepath = './temp/dev.ini'):
    ec2_asg = ec2_init(filepath, 'client', 'autoscaling')
    all_lc_img = dict()
    if ec2_asg.can_paginate('describe_launch_configurations'):
        paginator = ec2_asg.get_paginator('describe_launch_configurations')
        for i in paginator.paginate():
            for j in i['LaunchConfigurations']:
                if j['ImageId'] not in all_lc_img:
                    all_lc_img.setdefault(j['ImageId'],[j['LaunchConfigurationName']])
                else:
                    all_lc_img[j['ImageId']].append(j['LaunchConfigurationName'])
    all_asg_lc = set()
    response = ec2_asg.describe_auto_scaling_groups()
    for asg in response['AutoScalingGroups']:
        if 'LaunchConfigurationName' in asg:
            all_asg_lc.add(asg['LaunchConfigurationName'])

    ec2 = ec2_init(filepath, 'resource', 'ec2')
    existed_images = set(image for image in ec2.images.filter(Owners=[owner]))
    for image in existed_images:
        if image.image_id in all_lc_img:
            del all_lc_img[image.image_id]
    for lc_name in all_lc_img.values():
        for lst_index in lc_name:
            if lst_index not in all_asg_lc:
                ec2_asg.delete_launch_configuration(LaunchConfigurationName = lst_index)
    return 'delete lc not related from ami & asg'

def clean_vol(filepath = './temp/dev.ini'):
    ec2 = ec2_init(filepath, 'resource', 'ec2')
    spare_vols = set( volume for volume in ec2.volumes.all() if volume.state == 'available')  
    for vol in spare_vols:
        print (vol.delete())
        return 'delete avaiable volume in ec2'
""" vpc don't in instance& ifc& elb will
be deleted"""
def clean_vpc(filepath = './temp/dev.ini'):
    ec2 = ec2_init(filepath, 'resource', 'ec2')
    vpc_exempt = set()
    for instance in ec2.instances.all():
        vpc_exempt.add(instance.vpc_id)
    for ifc in ec2.network_interfaces.all():
        vpc_exempt.add(ifc.vpc_id)
    elb = ec2_init(filepath, 'client', 'elb')
    response = elb.describe_load_balancers()
    for lb in response['LoadBalancerDescriptions']:
        vpc_exempt.add(lb['VPCId'])
    vpc_delete = list()
    for vpc in ec2.vpcs.all():
        if vpc.vpc_id in vpc_exempt:
            continue
        elif vpc.vpc_id not in vpc_delete:
            vpc_delete.append(vpc.vpc_id)

    for subnet in ec2.subnets.filter(Filters = [{'Name': 'vpc-id', 'Values': vpc_delete}]):
        print (subnet.delete())
    for rtb in ec2.route_tables.filter(Filters = [{'Name': 'vpc-id', 'Values': vpc_delete}]):
        if len(rtb.associations_attribute) !=0 and rtb.associations_attribute[0]['Main']:
            continue
        else:
            print (rtb.delete())
    for vpc_id in vpc_delete:        
        for igw in ec2.internet_gateways.filter(Filters = [{'Name': 'attachment.vpc-id', 'Values': [vpc_id]}]):
            print (igw.detach_from_vpc(VpcId=vpc_id))
            print (igw.delete())
    for sg in ec2.security_groups.filter(Filters = [{'Name': 'vpc-id', 'Values': vpc_delete}]):
        for rule in sg.ip_permissions:
            if rule['UserIdGroupPairs'] != []:
                rule['IpRanges'] = []
                print (sg.revoke_ingress(IpPermissions = [rule], DryRun = False))
    for sg in ec2.security_groups.filter(Filters = [{'Name': 'vpc-id', 'Values': vpc_delete}]):
        if sg.group_name != 'default':
            print (sg.delete())

#        if sg.ip_permissions[0]['UserIdGroupPairs']
#        print (sg.delete())
    for acl in ec2.network_acls.filter(Filters = [{'Name': 'vpc-id', 'Values': vpc_delete}]):
        if acl.is_default:
            continue
        else:
            print (acl.delete())
    for vpc_id in vpc_delete:
        print (ec2.Vpc(vpc_id).delete())

    return 'clean subnet route tbl igw sg acl vpc of unsed one'
def clean_key(filepath = './temp/dev.ini'):
    ec2 = ec2_init(filepath, 'resource', 'ec2')
    key_exempt = set()
    for instance in ec2.instances.all():
        key_exempt.add(instance.key_name)
    asg = ec2_init(filepath, 'client', 'autoscaling')
    response = asg.describe_launch_configurations()
    for key_name in response['LaunchConfigurations']:
        if 'KeyName' in key_name:
            key_exempt.add(key_name['KeyName'])
    for key_pair in ec2.key_pairs.all():
        if key_pair.key_name in key_exempt:
            continue
        else:
            print (key_pair.delete())
    return 'clean unsed key'

def sg_in_use(filepath = './temp/dev.ini', sg_used = set()):
    previous = len(sg_used)
    ec2 = ec2_init(filepath, 'resource', 'ec2')
    for sg in ec2.security_groups.filter(Filters = [{'Name': 'group-id', 'Values': list(sg_used)}]):
        for rule in sg.ip_permissions:
            if rule['UserIdGroupPairs'] != []:
                for sg_id in rule['UserIdGroupPairs']:
                    sg_used.add(sg_id['GroupId'])
        for rule in sg.ip_permissions_egress:
            if rule['UserIdGroupPairs'] != []:
                for sg_id in rule['UserIdGroupPairs']:
                    sg_used.add(sg_id['GroupId'])
    after = len(sg_used)
    if previous == after:
        return sg_used
    else:
        return sg_in_use(filepath, sg_used)

def clean_sg(filepath = './temp/dev.ini'):
    ec2 = ec2_init(filepath, 'resource', 'ec2')
    sg_exempt = set()
    for instance in ec2.instances.all():
        for sg in instance.security_groups:
            sg_exempt.add(sg['GroupId'])
    for ifc in ec2.network_interfaces.all():
        for sg in ifc.groups:
            sg_exempt.add(sg['GroupId'])
    asg = ec2_init(filepath, 'client', 'autoscaling')
    response = asg.describe_launch_configurations()
    for lc in response['LaunchConfigurations']:
        if 'SecurityGroups' in lc:
            for sg in lc['SecurityGroups']:
                sg_exempt.add(sg)
    elb = ec2_init(filepath, 'client', 'elb')
    response = elb.describe_load_balancers()
    for elb in response['LoadBalancerDescriptions']:
        if 'SecurityGroups' in elb:
            for sg in elb['SecurityGroups']:
                sg_exempt.add(sg)
    for sg in ec2.security_groups.all():
        if sg.group_name == 'default':
            sg_exempt.add(sg.group_id)

    sg_all = set()
    for sg in ec2.security_groups.all():
        sg_all.add(sg.group_id)
        
    sg_used = sg_in_use(filepath, sg_exempt)    
    sg_del = set()
    sg_del = sg_all - sg_used
    for i in sg_del:
        if i in sg_all: 
            print (ec2.SecurityGroup(i).group_name)

    for sg in ec2.security_groups.filter(Filters = [{'Name': 'group-id', 'Values': list(sg_del)}]):
        for rule in sg.ip_permissions:
            if rule['UserIdGroupPairs'] != []:
                rule['IpRanges'] = []
                print (sg.revoke_ingress(IpPermissions = [rule], DryRun = False))
        for rule in sg.ip_permissions_egress:
            if rule['UserIdGroupPairs'] != []:
                rule['IpRanges'] = []
                print (sg.revoke_egress(IpPermissions = [rule], DryRun = False))
    for sg in sg_del:
        print (ec2.SecurityGroup(sg).delete())

def cloud_watch(filepath = './temp/dev.ini', volume_id = ''):
    end_time = datetime.now() + timedelta(days = 1)
    start_time = end_time - timedelta(days = 14)
    cloudwatch = ec2_init(filepath, 'client', 'cloudwatch')
    metrics = cloudwatch.get_metric_statistics(
            Namespace = 'AWS/EBS',
            MetricName = 'VolumeIdleTime',
            Dimensions = [{ 'Name': 'VolumeId', 'Value': volume_id}],
            Period = 3600,
            StartTime = start_time,
            EndTime = end_time,
            Statistics = ['Minimum'],
            Unit = 'Seconds'
    )
    return metrics['Datapoints']
def vol_statistics(filepath = './temp/dev.ini'):
    vol_cols = set()
    ec2 = ec2_init(filepath, 'resource', 'ec2')
#    rare_use = {cloud_watch(volume_id = volume.id): volume for volume in ec2.volumes.all() if volume.state == 'in-use'}
    rare_use = dict()
    for volume in ec2.volumes.all():
        if volume.state == 'in-use':
            if volume not in rare_use:
                rare_use.setdefault(volume, cloud_watch(volume_id = volume.id))
    for vol_stat in rare_use.values():
        counter = 0
        for per_date in vol_stat:
            if per_date['Minimum'] >= 299:
                counter += 1
        if len(vol_stat) != 0 and counter / len(vol_stat) == 1.0:
            vol_cols.add(list(rare_use.keys())[list(rare_use.values()).index(vol_stat)])
#            device =  rare_use_vol.attachments[0]['Device']
#            volume_id = rare_use_vol.attachments[0]['VolumeId']
#            print (counter / len(vol_stat), device, get_name(volume_id, filepath))
#        else:
#            rare_use_vol = list(rare_use.keys())[list(rare_use.values()).index(vol_stat)]
#            device =  rare_use_vol.attachments[0]['Device']
#            volume_id = rare_use_vol.attachments[0]['VolumeId']
#            print (counter / len(vol_stat), device, get_name(volume_id, filepath))
    return vol_cols
def get_instance_name(volume_id, filepath='./temp/dev.ini'):
    ec2 = ec2_init(filepath, 'resource', 'ec2')
    volume = ec2.Volume(volume_id)
    instance_id = volume.attachments[0]['InstanceId']
    instance = ec2.Instance(instance_id)
    for index in range(len(instance.tags)):
        if instance.tags[index]['Key'] == 'Name':
            return instance.tags[index]['Value']
    return None
def stat(filepath = './temp/dev.ini'):
    for volume in vol_statistics(filepath):
        if volume != None:
            print (volume.id, get_instance_name(volume.id, filepath), volume.attachments[0]['Device'])



if __name__ == '__main__':
    if len(sys.argv) < 3:
        print ('Usage: ',sys.argv[0],'clean_[ami|ss|vol|lc|vpc|key|sg]/stat [dev|stage|prodeu|produs]')
        sys.exit(2)
    filepath = './temp/'+sys.argv[2]+'.ini'
    if os.path.exists(filepath):
        getattr(sys.modules[__name__], sys.argv[1])(filepath)
    else:
        print ('config file do not exists, quit!')
        sys.exit(2)
