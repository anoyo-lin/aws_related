#!/bin/bash
aws cloudformation deploy --template-file s3.yaml --stack-name ssm-ami-project-s3 --capabilities CAPABILITY_NAMED_IAM --parameter-overrides BucketName=ssm-ami-project-prodeu Environment=prodeu
export SCRIPTBUCKET=`aws cloudformation describe-stacks --stack-name ssm-ami-project-s3|jq -r '.Stacks[0].Outputs[0].OutputValue'`
aws s3 cp ssm_ami.zip s3://$SCRIPTBUCKET
aws cloudformation deploy --template-file lambda.yaml --stack-name ssm-ami-project-lambda --capabilities CAPABILITY_NAMED_IAM --parameter-overrides SrcAmi=ami-redacted Environment=prodeu
# change the environment and bucketName and srcAMI
