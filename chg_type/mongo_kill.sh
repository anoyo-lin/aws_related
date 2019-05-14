#/bin/bash
#set -x
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
function mongo_stop(){
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
echo 'mongodb had already stopped'
sleep 5
else
cnt=1
while [[ \$(/opt/app/mongodb/bin/mongo --quiet --eval 'JSON.stringify(db.isMaster())'|jq -r .ismaster) == 'true' ]]
do
/opt/app/mongodb/bin/mongo --quiet --eval 'rs.stepDown()'
echo "trying to step down primary \${cnt} times."
((cnt+=1))
sleep 5
done
while [[ \$(/opt/app/mongodb/bin/mongo --quiet --eval 'JSON.stringify(db.isMaster())'|jq -r .primary) == 'null' ]]
do
echo 'primary replica set election completing. '
sleep 5
done
if [[ \$(/opt/app/mongodb/bin/mongo --quiet --eval 'JSON.stringify(db.isMaster())'|jq -r .ismaster) == 'false' ]] && [[ \$(/opt/app/mongodb/bin/mongo --quiet --eval 'JSON.stringify(db.isMaster())'|jq -r .primary) != 'null' ]]
then
/opt/app/mongodb/bin/mongo --quiet --eval 'rs.status()'
/opt/app/mongodb/bin/mongo admin --quiet --eval 'db.shutdownServer()'
fi
fi
END_STOP
EOF
}
function mongo_start(){
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
ssh ubuntu@${IP} /bin/bash << 'END_START'
/etc/init.d/mongodb start
sleep 10 
sync
/opt/app/mongodb/bin/mongo --quiet --eval 'rs.status()'
END_START
EOF
}
if [[ $1 == '' ]] || [[ $2 == '' ]] || [[ $3 == '' ]]
then
	echo "Usage: $0 instance-id dev method[start/stop]"
	exit -1
fi
case "$3" in
	'start' )
		mongo_start $1 $2
		;;
	'stop' )
		mongo_stop $1 $2
		;;
	*)
		echo "Usage: $0 instance-id dev method[start/stop]"
        	exit -1
		;;
esac
