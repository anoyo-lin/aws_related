#/bin/bash
set -x
: 'it need to define the ssh config at ~/.ssh/config
it can start/stop mongodb from local ==> bastion ==> target
example of ssh config file:
Host dev
StrictHostKeyChecking no
ForwardAgent yes
Hostname 54.236.225.95
User ubuntu
ProxyCommand /bin/connect-proxy -H proxy.redacted.net:8080 %h %p
IdentityFile /home/88881782/.ssh/my_key
'
function mongo_kill(){
#	if [[ "$2" == 'dev' ]]
#	then
#		ssh_acc='ubuntu'
#	else
#		ssh_acc='gene'
#	fi
    if [[ $( aws ec2 describe-instances --instance-ids=$1 --profile $2 2>&1 | grep -c '.*error.*' ) == 1 ]] || [[ $2 == '' ]]
    then
        echo 'no matched instance id found, quit!'
        echo 'Usage: ./mongo_kill.sh i-7061789c dev'
        exit -1
    else
        IP=$(aws ec2 describe-instances --instance-ids=$1 --profile $2 --query 'Reservations[0].Instances[0].PrivateIpAddress'|tr -d '"')
    fi
ssh $2 << EOF
sudo su - ubuntu   
ssh ubuntu@${IP} /bin/bash << 'END_STOP'
if [[ \$(ps -ef|grep mongo|grep -v grep) == '' ]]
then
/etc/init.d/mongodb start
sleep 5
/opt/app/mongodb/bin/mongo --quiet --eval 'rs.status()'
else
/opt/app/mongodb/bin/mongo --quiet --eval 'rs.status()'
fi
END_STOP
EOF
}
mongo_kill $1 $2
