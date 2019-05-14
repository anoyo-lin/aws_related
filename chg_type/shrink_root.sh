#!/bin/bash
#set -x
#rsync -aHAXxSP /mnt/root_src/ /mnt/root_target
#dd if=/dev/xvda of=/dev/xvdz count=1
#echo "- - -" > /sys/class/scsi_host/host1/scan
#echo -e "n\\np\\n\\n\\nw\\n" | fdisk /dev/xvdz
#mkfs.ext4 /dev/xvdz
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
sudo su -
if [[ \$(parted /dev/xvda p|sed -n '/^Part.*/p'|awk '{print \$3}') == 'gpt' ]]
then
dd if=/dev/xvda of=/dev/xvdz count=4096
echo "- - -" > /sys/class/scsi_host/host1/scan
echo -e "x\\ne\\nm\\nd\\n1\\nw\\nY\\n" | gdisk /dev/xvdz
echo -e "n\\n1\\n\\n\\n\\np\\nw\\nY\\n" | gdisk /dev/xvdz
elif [[ \$(parted /dev/xvda p|sed -n '/^Part.*/p'|awk '{print \$3}') == 'msdos' ]]
then
dd if=/dev/xvda of=/dev/xvdz count=1
dd if=/dev/zero of=/dev/xvdz seek=1 count=2047
echo "- - -" > /sys/class/scsi_host/host1/scan
echo -e "d\\nn\\np\\n\\n\\n\\np\\nw\\nq" | fdisk /dev/xvdz
else
echo "not found suitable filesystem, quit!"
exit -1
fi
sleep 5
mkfs.ext4 /dev/xvdz1
mkdir /mnt/target
mount /dev/xvdz1 /mnt/target
rsync -aHAXxS --partial --exclude '/dev/*' --exclude '/proc/*' --exclude '/sys/*' --exclude '/mnt/target' / /mnt/target
if [[ \$(cat /etc/os-release|sed -n '/^NAME.*/p'|sed -n '/Amazon/p') == '' ]]
then
for x in 'dev' 'proc' 'sys'; do mount --bind /\$x /mnt/target/\$x; done
chroot /mnt/target /bin/bash -c 'update-grub; grub-install /dev/xvdz'
fi
e2label /dev/xvdz1 /
END_UPG
END
}

function waiter(){
	if [[ $1 == '' ]] || [[ $2 == '' ]] || [[ $3 == '' ]] || [[ $4 == '' ]]
	then
		echo "Usage: $0 completed snapshot-id dev type"
		exit -1
	fi
	state='none'
	while [[ $state != $1 ]]
	do
		echo "waiting $4 $2 is going to $1 at enviroment $3"
		case "$4" in
		"snapshot" )
			state=$(aws ec2 describe-snapshots --profile $3 --snapshot-ids $2 | jq -r '.Snapshots[].State')
			progress=$(aws ec2 describe-snapshots --profile $3 --snapshot-ids $2 | jq -r '.Snapshots[].Progress')
			echo "Complete percentage ${progress}"
		;;
		"volume" )
        		state=$(aws ec2 describe-volumes --profile $3 --volume-ids $2|jq -r '.Volumes[].State')
		;;
		"instance" )
			state=$(aws ec2 describe-instances --profile $3 --instance-ids $2|jq -r '.Reservations[].Instances[].State.Name')
		;;
		* )
                	echo "Usage: $0 completed snapshot-id dev type"
                	exit -1
		;;
		esac
		sleep 5 
	done
}

if [[ $1 == '' ]] || [[ $2 == '' ]] || [[ $3 == '' ]]
then
	echo "Usage: $0 instance-id dev shrink_vol_size(GiB)"
	exit -1
fi
./mongo_kill.sh $1 $2 stop
#root=/dev/sda src=/dev/sdy target=/dev/sdz 
root=$(aws ec2 describe-instances --profile $2 | jq -r ".Reservations[].Instances[]|select(.InstanceId==\"$1\")|.RootDeviceName")
#src=$(echo ${root}|sed -n 's/\(^\/dev\/.*d\)[a-z].*/\1y/p')
target=$(echo ${root}|sed -n 's/\(^\/dev\/.*d\)[a-z].*/\1z/p')
#some parameter of root volume (id,az,type)
vol_id=$(aws ec2 describe-instances --profile $2 --instance-ids $1 | jq -r ".Reservations[].Instances[].BlockDeviceMappings[]|select(.DeviceName==\"${root}\")|.Ebs.VolumeId")
az=$(aws ec2 describe-volumes --profile $2 --volume-ids ${vol_id}|jq -r .Volumes[].AvailabilityZone)
vol_type=$(aws ec2 describe-volumes --profile $2 --volume-ids ${vol_id}|jq -r .Volumes[].VolumeType)
instance_name=$(aws ec2 describe-instances --profile $2 --instance-ids $1 | jq -r '.Reservations[].Instances[].Tags[]|select(.Key=="Name")|.Value')
disk_label=$(echo ${root}|awk -F/ '{print $3}')
#stop
#aws ec2 stop-instances --instance-ids $1 --profile $2
#waiter 'stopped' $1 $2 'instance'
#create snap
#snap_id=$(aws ec2 create-snapshot --profile $2 --volume-id ${vol_id} | jq -r '.SnapshotId')
#waiter 'completed' ${snap_id} $2 'snapshot'
#src_vol_id=$(aws ec2 create-volume --profile $2 --volume-type ${vol_type} --availability-zone ${az} --snapshot-id ${snap_id}|jq -r '.VolumeId')
#waiter 'available' ${src_vol_id} $2 'volume'
shrink_vol_id=$(aws ec2 create-volume --profile $2 --volume-type ${vol_type} --availability-zone ${az} --size $3 --tag-specifications "ResourceType=volume,Tags=[{Key=Name,Value=shrinked_${instance_name}_${disk_label}}]"|jq -r '.VolumeId')
waiter 'available' ${shrink_vol_id} $2 'volume'
#start
#aws ec2 start-instances --instance-ids $1 --profile $2
#waiter 'running' $1 $2 'instance'
#aws ec2 attach-volume --volume-id ${src_vol_id} --instance-id $1 --device ${src} --profile $2
#waiter 'in-use' ${src_vol_id} $2 'volume'
aws ec2 attach-volume --volume-id ${shrink_vol_id} --instance-id $1 --device ${target} --profile $2
#waiter 'in-use' ${shrink_vol_id} $2 'volume'

get_info $1 $2
#stop
aws ec2 stop-instances --instance-ids $1 --profile $2
waiter 'stopped' $1 $2 'instance'
#detach
aws ec2 detach-volume --volume-id ${shrink_vol_id} --profile $2
#waiter 'available' ${shrink_vol_id} $2 'volume'
aws ec2 detach-volume --volume-id ${vol_id} --profile $2
#waiter 'available' ${vol_id} $2 'volume'
#aws ec2 detach-volume --volume-id ${src_vol_id} --profile $2
#waiter 'available' ${src_vol_id} $2 'volume'
#attach
aws ec2 attach-volume --volume-id ${shrink_vol_id} --instance-id $1 --device ${root} --profile $2
#waiter 'in-use' ${shrink_vol_id} $2 'volume'
#start
aws ec2 start-instances --instance-ids $1 --profile $2
waiter 'running' $1 $2 'instance'
./mongo_kill.sh $1 $2 start
