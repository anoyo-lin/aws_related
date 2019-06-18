# aws_related
cdn directory contains the CDN log project for the log statistics of HTTP status code ETL extract from edgecast customer origin thru the sftp. and re-arrange it into AWS s3. and taking advantage of AWS Athena to collect and make the report for routine analyze and impact pre-calculation.sending alert e-mail thru AWS SES to stakeholder ASAP.
chg_type is script for instance tier upgrade, and mongodb maintenance and a innovation for the AWS EBS disk volume size shrinking.
opswork is the legacy project. created by ex-colleague to keep the ssh-user in-time. i have little research on the area of chef and puppet, only have the function integrated with OPSWORK usage, but i believe if i can be handed over some project with chef puppet, i can manage to use opswork to solve the problem on aws platform.
SSM directory is project to let the autoscaling group instance auto renewing and update, when the new AMI creation some shell script will executed and we can put some heavy processing from the instance initialization into the AMI to fast forward the whole process of instance boot up, the sophisticated SSM use case contain the SSM self-defined document/lambda with python.
aws_helper can list the necessary information for AWS EC2
ec2_clean can clean up the unused the resources of AWS EC2, keep the VPC clean and simple.
gen_instance can create/clone the instance in covenient and fast way.
