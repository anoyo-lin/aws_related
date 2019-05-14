#!/bin/bash
set -x
#it need to redirect stderr to stdout to capture the error txt pattern
#grep -c will return 1/0 it stands for true/false.

function load_drv(){
    if [[ $( aws ec2 describe-instances --instance-ids=$1 --profile $2 2>&1 | grep -c '.*error.*' ) == 1 ]] || [[ $2 == '' ]]
    then
        echo 'no matched instance id found, quit!'
        exit -1
    else
        IP=$(aws ec2 describe-instances --instance-ids=$1 --profile $2 --query 'Reservations[0].Instances[0].PrivateIpAddress'|tr -d '"')
    fi
ssh $2 << EOF
sudo su - ubuntu
ssh ubuntu@${IP} /bin/bash << 'END_UPG'
sudo apt-get update && sudo apt-get upgrade -y
END_UPG
ssh ubuntu@${IP} /bin/bash << 'END_INST'
sudo apt-get install -y build-essential dkms git
END_INST
ssh ubuntu@${IP} /bin/bash << 'END_GIT'
git clone https://github.com/amzn/amzn-drivers
END_GIT
ssh ubuntu@${IP} /bin/bash << 'END_BUILD'
[ ! -d '/usr/src/amzn-drivers-1.0.0' ] && { sudo mv 'amzn-drivers' '/usr/src/amzn-drivers-1.0.0'; } || { sudo rm -fr '/usr/src/amzn-drivers-1.0.0'; sudo mv 'amzn-drivers' '/usr/src/amzn-drivers-1.0.0'; }
sudo touch /usr/src/amzn-drivers-1.0.0/dkms.conf
sudo chmod 777 /usr/src/amzn-drivers-1.0.0/dkms.conf
echo '/usr/src/amzn-drivers-1.0.0/dkms.conf' > /usr/src/amzn-drivers-1.0.0/dkms.conf
echo 'PACKAGE_NAME="ena"' >> /usr/src/amzn-drivers-1.0.0/dkms.conf
echo 'PACKAGE_VERSION="1.0.0"' >> /usr/src/amzn-drivers-1.0.0/dkms.conf
echo 'CLEAN="make -C kernel/linux/ena clean"' >> /usr/src/amzn-drivers-1.0.0/dkms.conf
echo 'MAKE="make -C kernel/linux/ena/ BUILD_KERNEL=\${kernelver}"' >> /usr/src/amzn-drivers-1.0.0/dkms.conf
echo 'BUILT_MODULE_NAME[0]="ena"' >> /usr/src/amzn-drivers-1.0.0/dkms.conf
echo 'BUILT_MODULE_LOCATION="kernel/linux/ena"' >> /usr/src/amzn-drivers-1.0.0/dkms.conf
echo 'DEST_MODULE_LOCATION[0]="/updates"' >> /usr/src/amzn-drivers-1.0.0/dkms.conf
echo 'DEST_MODULE_NAME[0]="ena"' >> /usr/src/amzn-drivers-1.0.0/dkms.conf
echo 'AUTOINSTALL="yes"' >> /usr/src/amzn-drivers-1.0.0/dkms.conf
sudo dkms add -m amzn-drivers -v 1.0.0
sudo dkms build -m amzn-drivers -v 1.0.0
sudo dkms install -m amzn-drivers -v 1.0.0
sudo update-initramfs -c -k all
modinfo ena
modinfo nvme
END_BUILD
ssh ubuntu@${IP} /bin/bash << 'END_FS'
sudo sed -i 's/xvd/nvme/g' /etc/fstab
alpha=({a..z})
for i in {1..26}
do
sudo sed -i "s/nvme\${alpha[\$((\${i}-1))]}/nvme\${i}n1/g" /etc/fstab
done
END_FS
EOF
}
function ena_support() {
        if [[ $( aws ec2 describe-instances --instance-ids=$1 --profile $2 2>&1 | grep -c '.*error.*' ) == 1 ]]
        then
                echo 'no matched instance id found, quit!'
                exit -1
        fi
		if [[ $2 == '' ]]
		then
				echo 'wrong enviroment, quit!'
				exit -1
		fi
        aws ec2 stop-instances --instance-ids $1 --profile $2
        #aws return json can extract list [] with name.[*/0]; extract { 'key': 'value'} with name.key
        stat_code=0
        while [ $stat_code -ne 80 ]
        do
                stat_code=$(aws ec2 stop-instances --instance-ids $1 --profile $2 --query 'StoppingInstances[*].PreviousState.Code')
                stat_code=$(echo $stat_code | tr -d '" []')
                sleep 10
        done

        aws ec2 modify-instance-attribute --instance-id $1 --ena-support --profile $2
	aws ec2 modify-instance-attribute --instance-id $1 --instance-type "{\"Value\": \"m5.large\"}" --profile $2
	sleep 10
        aws ec2 start-instances --instance-ids $1 --profile $2
        return 0
}

load_drv $1 $2
ena_support $1 $2
