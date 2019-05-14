#!/usr/bin/env python3
import os, sys
import boto3
import shutil
import urllib.request
import zipfile
import subprocess
from datetime import datetime, timezone

#rec1.uep sender.uep push-test.uep

def main(env='systest'):    
    app_list = { 'push': { 'name': 'uep_push', 'url': 'push-test.uep', 'zip': 'ver-autodeploy-ueppush' }, 'sender': { 'name':'requestbuffer-sender', 'url': 'sender.uep', 'zip': 'ver-autodeploy-requestbuffersender' }, 'receiver': { 'name': 'requestbuffer-receiver', 'url': 'rec1.uep', 'zip': 'ver-autodeploy-requestbufferreceiver' } }
    for app in app_list:
        # if os.path.exists('/home/ubuntu/s3/am-operation/{0}/uep-app-{1}/opt/app/{2}/webapps'.format(env, app, app_list[app]['name'])):
        #     url = 'http://{0}:8080/{1}/services/info/version'.format(app_list[app]['url'], app_list[app]['name'])
        #     try:
        #         version = urllib.request.urlopen(url).read().decode('utf-8')
        #         print('# {} is running with version: {}'.format(app, version))
        #     except:
        #         print('# {} version NOT available'.format(app))

        if os.path.exists('/tmp/{1}_{0}_autodeploy.version_id'.format(app, env)):
            with open('/tmp/{1}_{0}_autodeploy.version_id'.format(app, env)) as f:
                version_old = f.read()
        else:
            version_old = ''
        s3 = boto3.resource('s3')
        bucket_name = 'autodeploy-test'
        version_new = s3.Object(bucket_name, "{}.zip".format(app_list[app]['zip'])).version_id
        print('old version vs new version: "{0}" vs "{1}"'.format(version_old, version_new))
        if version_old == version_new:
            time_modified = s3.Object(bucket_name, "{}.zip".format(app_list[app]['zip'])).last_modified
            time_delta = datetime.now(timezone.utc) - time_modified
            print("## NO new package of {} to deploy, modified {} seconds ago at {}.".format(app, time_delta.seconds, time_modified.strftime('%Y-%m-%d %H:%M:%S')))
            print('{}\n# autodeploy ends ...\n'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            continue
        else:
            print('## Running autodeploy of {} with new version "{}"'.format(app, version_new))
            s3_client = boto3.client('s3')
            transfer = boto3.s3.transfer.S3Transfer(s3_client)
            transfer.download_file(bucket_name, "{}.zip".format(app_list[app]['zip']), '/tmp/{0}.zip'.format( app_list[app]['zip']))
            with zipfile.ZipFile('/tmp/{0}.zip'.format( app_list[app]['zip'])) as zf:
                zf.extractall('/tmp/')
            shutil.copyfile("/tmp/{}.war".format(app_list[app]['name']), '/home/ubuntu/s3/am-operation/{0}/uep-app-{1}/opt/app/{2}/webapps/{2}.war'.format(env, app, app_list[app]['name']))
            with open('/tmp/{1}_{0}_autodeploy.version_id'.format(app, env), 'wt') as f:
                f.write(version_new)
            command = '/home/ubuntu/s3/am-operation/operation.sh up'
            subprocess.call(command, shell=True)
            os.remove('/tmp/{0}.zip'.format( app_list[app]['zip']))
            os.remove('/tmp/{0}.war'.format( app_list[app]['name']))
def usage():
    print ('Usage: {0} env, env is in [systest, stage, test, prod]'.format(sys.argv[0]))

if __name__ == '__main__':
    argv_lst = [ 'systest', 'stage' , 'test', 'prod' ]
    if len(sys.argv) != 2:
        usage()
        sys.exit(-1)
    else:
        if sys.argv[1] not in argv_lst:
            usage()
            sys.exit(-1)

    env=sys.argv[1]
    print('# autodeploy starts ... {}'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    main(env)
    print('# autodeploy ends ... {}'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
