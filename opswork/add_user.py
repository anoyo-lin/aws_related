#!/usr/bin/python3
import boto3
import sys, os
def del_users(arn):
    try:
        response = client.delete_user_profile(
                IamUserArn = arn 
                )
    except Exception as e:
        return 'error occured! {0}'.format(e)
    return response

def grant_perm(stack_id, user):
    
    try:
        response = client.set_permission(
                StackId = stack_id,
                IamUserArn = user['IamUserArn'],
                AllowSsh = True,
                AllowSudo = True,
                Level = 'iam_only'
                )
    except Exception as e:
        return 'error occured! {0}'.format(e)
    return response

def add_users(stack_id, user):
    try:
        client.describe_user_profiles(
                IamUserArns = [
                    user['IamUserArn']
                    ]
                )
    except:
        response = client.create_user_profile(
                IamUserArn = user['IamUserArn'],
                SshUsername = user['SshUsername'],
                SshPublicKey = user['SshPublicKey'],
                AllowSelfManagement = user['AllowSelfManagement']
                )
        print (response)
        print (grant_perm(stack_id, user))
    response = client.update_user_profile(
            IamUserArn = user['IamUserArn'],
            SshUsername = user['SshUsername'],
            SshPublicKey = user['SshPublicKey'],
            AllowSelfManagement = user['AllowSelfManagement']
            )
    print (response)
#    print (grant_perm(stack_id, user))

if __name__ == '__main__':
    import adfs
    import user_list 
    
    region = adfs.region
    aws_account = adfs.env[sys.argv[1]][1]
    somc = list()
    domain_grp = adfs.role_arn.split('/')[1]
    for user_name in user_list.profile:
        somc.append(
            {
                "IamUserArn": "arn:aws:sts::{0}:assumed-role/{2}/{1}".format(aws_account, user_name, domain_grp),
                "Name": "ADFS-console-sysop-G/{0}".format(user_name),
                "SshUsername": "adfs-console-sysop-g-{0}".format(user_name),
                "SshPublicKey": "{0}".format(user_list.profile[user_name]),
                "AllowSelfManagement": True
                }
            )
    stack_id = user_list.stack[sys.argv[1]]

    session = boto3.Session(region_name = region)
    client = session.client('opsworks')
    for user in somc:
        if 'IamUserArn' in user:
            add_users(stack_id, user)
    import re
    pattern = re.compile('.*-sysop-G.*')
    server_arn_lst = set(arn['IamUserArn'] for arn in client.describe_user_profiles()['UserProfiles'] if pattern.search(arn['IamUserArn']))
    current_arn_lst = set(arn['IamUserArn'] for arn in somc)
    remove_arn_lst = server_arn_lst - current_arn_lst
    for arn in remove_arn_lst:
        print(del_users(arn))
