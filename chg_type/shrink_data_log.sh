#!/bin/bash
set -x
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
    	sleep 3 
	done
}
if [[ $1 == '' ]] || [[ $2 == '' ]]  
then
	echo "Usage: $0 instance-id profile"
	exit -1
fi

data_mnt_pts='/opt/data'
log_mnt_pts='/opt/logs'
data_size=2
data_type='gp2'
log_size=1
log_type='standard'

./mongo_kill.sh $1 $2 stop

get_info $1 $2 > temp
sed -i 1,/^Filesystem/d temp

data_mnt_pts_1=$(echo $data_mnt_pts|sed -n 's/\//\\\//gp')
log_mnt_pts_1=$(echo $log_mnt_pts|sed -n 's/\//\\\//gp')
data_src_suffix=$(cat temp|sed -n "/${data_mnt_pts_1}/p"|awk '{print $1}'|sed -n 's/\/dev\/.*\(d[a-z]\)/\1/p')
log_src_suffix=$(cat temp|sed -n "/${log_mnt_pts_1}/p"|awk '{print $1}'|sed -n 's/\/dev\/.*\(d[a-z]\)/\1/p')
data_tar_suffix='df'
log_tar_suffix='dg'
data_tar_dev=$(cat temp | sed -n "/${data_mnt_pts_1}/p" | awk '{print $1}'|sed -n "s/\(^\/dev\/.*d\)[a-z]/\1f/p")
log_tar_dev=$(cat temp | sed -n "/${log_mnt_pts_1}/p" | awk '{print $1}'|sed -n "s/\(^\/dev\/.*d\)[a-z]/\1g/p")
instance_name=$(aws ec2 describe-instances --profile $2 --instance-ids $1| jq -r '.Reservations[].Instances[].Tags[]|select(.Key=="Name")|.Value')
rm temp
data_vol_id=$(aws ec2 describe-volumes --profile $2 --filters Name=attachment.instance-id,Values=$1|jq -r ".Volumes[].Attachments[]|select(.Device|endswith(\"${data_src_suffix}\"))|.VolumeId")
log_vol_id=$(aws ec2 describe-volumes --profile $2 --filters Name=attachment.instance-id,Values=$1|jq -r ".Volumes[].Attachments[]|select(.Device|endswith(\"${log_src_suffix}\"))|.VolumeId")
data_tar_dev_aws=$(aws ec2 describe-volumes --profile $2 --volume-ids ${data_vol_id}|jq -r '.Volumes[].Attachments[].Device'|sed -n 's/\(^\/dev.*d\)[a-z].*/\1/p')f
log_tar_dev_aws=$(aws ec2 describe-volumes --profile $2 --volume-ids ${data_vol_id}|jq -r '.Volumes[].Attachments[].Device'|sed -n 's/\(^\/dev.*d\)[a-z].*/\1/p')g
data_disk_label=$(echo ${data_tar_dev_aws}|awk -F/ '{print $3}')
log_disk_label=$(echo ${log_tar_dev_aws}|awk -F/ '{print $3}')
az=$(aws ec2 describe-volumes --profile $2 --volume-ids ${data_vol_id}|jq -r .Volumes[].AvailabilityZone)
#data_vol_type=$(aws ec2 describe-volumes --profile $2 --volume-ids ${data_vol_id}|jq -r .Volumes[].VolumeType)
#log_vol_type=$(aws ec2 describe-volumes --profile $2 --volume-ids ${log_vol_id}|jq -r .Volumes[].VolumeType)
new_data_vol_id=$(aws ec2 create-volume --profile $2 --size ${data_size} --volume-type ${data_type} --availability-zone ${az} --tag-specifications "ResourceType=volume,Tags=[{Key=Name,Value=shrinked_${instance_name}_${data_disk_label}}]"|jq -r '.VolumeId')
waiter 'available' ${new_data_vol_id} $2
new_log_vol_id=$(aws ec2 create-volume --profile $2 --size ${log_size} --volume-type ${log_type} --availability-zone ${az} --tag-specifications "ResourceType=volume,Tags=[{Key=Name,Value=shrinked_${instance_name}_${log_disk_label}}]"|jq -r '.VolumeId')
waiter 'available' ${new_log_vol_id} $2
aws ec2 attach-volume --volume-id ${new_data_vol_id} --instance-id $1 --device ${data_tar_dev_aws} --profile $2
waiter 'in-use' ${new_data_vol_id} $2
aws ec2 attach-volume --volume-id ${new_log_vol_id} --instance-id $1 --device ${log_tar_dev_aws} --profile $2
waiter 'in-use' ${new_log_vol_id} $2

ssh $2 << END
sudo su - ubuntu
ssh ubuntu@${IP} << 'EXTEND'
sudo mkdir /mnt/data
sudo mkdir /mnt/logs
sudo mkfs -t ext4 ${data_tar_dev}
sleep 3
sync
sudo mkfs -t ext4 ${log_tar_dev}
sleep 3 
sync
sudo mount ${data_tar_dev} /mnt/data
sleep 3
sync
sudo mount ${log_tar_dev} /mnt/logs
sleep 3 
sync
sudo rsync -aHAXxS --partial ${data_mnt_pts}/ /mnt/data
sudo rsync -aHAXxS --partial ${log_mnt_pts}/ /mnt/logs
sudo umount -l ${data_mnt_pts}
sleep 3
sync
sudo umount -l ${log_mnt_pts}
sleep 3
sync
sudo umount /mnt/data
sleep 3
sync
sudo umount /mnt/logs
sleep 3
sync 
sudo mount ${data_tar_dev} ${data_mnt_pts}
sleep 3
sync
sudo mount ${log_tar_dev} ${log_mnt_pts}
sleep 3 
sync
sudo sed -i "s/\(^\/dev.*\)${data_src_suffix}\([[:space:]].*\)/\1${data_tar_suffix}\2/" /etc/fstab
sudo sed -i "s/\(^\/dev.*\)${log_src_suffix}\([[:space:]].*\)/\1${log_tar_suffix}\2/" /etc/fstab
sudo cat /etc/fstab
df -h
EXTEND
END
aws ec2 detach-volume --volume-id ${data_vol_id} --profile $2
waiter 'available' ${data_vol_id} $2
aws ec2 detach-volume --volume-id ${log_vol_id} --profile $2
waiter 'available' ${log_vol_id} $2

./mongo_kill.sh $1 $2 start
