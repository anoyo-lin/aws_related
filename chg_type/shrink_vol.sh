#!/bin/bash
#set -x
function get_info(){
	if [[ $1 == '' ]] || [[ $2 == '' ]]
	then
		echo "Usage: $0 instance-id profile"
		exit -1
	fi
	if [[ $( aws ec2 describe-instances --instance-ids=$1 --profile $2 2>&1 | grep -c '.*error.*' ) == 1 ]] || [[ $2 == '' ]]
	then
       		echo 'no matched instance id found, quit!'
        	exit -1
    	else
        IP=$(aws ec2 describe-instances --instance-ids=$1 --profile $2 --query 'Reservations[0].Instances[0].PrivateIpAddress'|tr -d '"')
    	fi
ssh $2 << END 
sudo su - ubuntu
ssh ubuntu@${IP} /bin/bash << 'END_UPG'
df -h
END_UPG
END
}
function waiter(){
	if [[ $1 == '' ]] || [[ $2 == '' ]] || [[ $3 == '' ]]
	then
		echo "Usage: $0 available/in-use volume-id profile"
		exit 1
	fi
	state='none'
	while [[ $state != $1 ]]
	do
	echo "waiting $3's volume $2 change to $1..."
    	state=$(aws ec2 describe-volumes --profile $3 --volume-ids $2|jq -r '.Volumes[].State')
    	sleep 10
	done
}
if [[ $1 == '' ]] || [[ $2 == '' ]]  
then
	echo "Usage: $0 instance-id profile"
	exit -1
fi
./mongo_kill.sh $1 $2 stop
get_info $1 $2 > temp
sed -i 1,/^Filesystem/d temp
cat temp
echo "please specified the line of volume you want to change" && read line && echo "you selected $line, if correct press any key to continue." && read
echo "please specified disk size you want to change" && read size && echo "you clarified ${size}GiB, if correct press any key to continue." && read
echo "please specified disk label you want to change" && read label && echo "you clarified ${label} as disk ending label, if correct press any key to continue." && read
echo "please specified disk type you want to change" && read vol_type && echo "you clarified ${vol_type} as disk ending label, if correct press any key to continue." && read
if [[ ${vol_type} == 'io1' ]]
then
	echo "please specified io1 iops you want to change" && read iops && echo "you clarified ${iops} as disk iops, if correct press any key to continue." && read
fi
mnt_pts=$(sed -n "${line}"p temp | awk '{print $6}')
src_suffix=$(sed -n "${line}"p temp | awk '{print $1}'|sed -n 's/^\/dev\/.*\(d[a-z]\)/\1/p')
tar_suffix='d'${label}
tar_dev=$(sed -n "${line}"p temp | awk '{print $1}'|sed -n "s/\(^\/dev\/.*d\)[a-z]/\1${label}/p")
instance_name=$(aws ec2 describe-instances --profile $2 --instance-ids $1| jq -r '.Reservations[].Instances[].Tags[]|select(.Key=="Name")|.Value')
rm temp
vol_id=$(aws ec2 describe-volumes --profile $2 --filters Name=attachment.instance-id,Values=$1|jq -r ".Volumes[].Attachments[]|select(.Device|endswith(\"${src_suffix}\"))|.VolumeId")
tar_dev_aws=$(aws ec2 describe-volumes --profile $2 --volume-ids ${vol_id}|jq -r '.Volumes[].Attachments[].Device'|sed -n 's/\(^\/dev.*d\)[a-z].*/\1/p')${label}
disk_label=$(echo ${tar_dev_aws}|awk -F/ '{print $3}')
az=$(aws ec2 describe-volumes --profile $2 --volume-ids ${vol_id}|jq -r .Volumes[].AvailabilityZone)
#vol_type=$(aws ec2 describe-volumes --profile $2 --volume-ids ${vol_id}|jq -r .Volumes[].VolumeType)
if [[ ${vol_type} == 'io1' ]]
then
	new_vol_id=$(aws ec2 create-volume --profile $2 --size ${size} --volume-type ${vol_type} --iops ${iops} --availability-zone ${az} --tag-specifications "ResourceType=volume,Tags=[{Key=Name,Value=shrinked_${instance_name}_${disk_label}}]"|jq -r '.VolumeId')
else
	new_vol_id=$(aws ec2 create-volume --profile $2 --size ${size} --volume-type ${vol_type} --availability-zone ${az} --tag-specifications "ResourceType=volume,Tags=[{Key=Name,Value=shrinked_${instance_name}_${disk_label}}]"|jq -r '.VolumeId')
fi
waiter 'available' ${new_vol_id} $2
aws ec2 attach-volume --volume-id ${new_vol_id} --instance-id $1 --device ${tar_dev_aws} --profile $2
waiter 'in-use' ${new_vol_id} $2
ssh $2 << END
sudo su - ubuntu
ssh ubuntu@${IP} << 'EXTEND'
sudo mkdir /mnt/shrink
sudo mkfs -t ext4 ${tar_dev}
sleep 5
sudo mount ${tar_dev} /mnt/shrink
sleep 5
sudo rsync -aHAXxS --partial ${mnt_pts}/ /mnt/shrink
sleep 5 
sudo umount -l ${mnt_pts}
sleep 5
sudo umount /mnt/shrink
sleep 5
sudo mount ${tar_dev} ${mnt_pts}
sleep 5
sudo sed -i "s/\(^\/dev.*\)${src_suffix}\([[:space:]].*\)/\1${tar_suffix}\2/" /etc/fstab
sudo cat /etc/fstab
df -h
EXTEND
END
aws ec2 detach-volume --volume-id ${vol_id} --profile $2
waiter 'available' ${vol_id} $2
./mongo_kill.sh $1 $2 start
