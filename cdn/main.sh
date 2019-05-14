#!/bin/bash
SCRIPTBUCKET='redacted'
CDNLST=''
APPLST=''


#aws cloudformation deploy --template-file s3.yaml --stack-name cdn-log-project-s3 --capabilities CAPABILITY_NAMED_IAM --parameter-overrides BucketName=$SCRIPTBUCKET
#export SCRIPTBUCKET=`aws cloudformation describe-stacks --stack-name cdn-log-project-s3|jq -r '.Stacks[0].Outputs[0].OutputValue'`
aws s3 cp cdn_log.zip s3://$SCRIPTBUCKET
aws s3 cp id_rsa_cdn_logs s3://$SCRIPTBUCKET/key/
#aws cloudformation deploy --template-file athena.yaml --stack-name cdn-log-project-athena --capabilities CAPABILITY_NAMED_IAM --parameter-overrides KeyBucket=$SCRIPTBUCKET
aws cloudformation deploy --template-file lambda.yaml --stack-name cdn-log-project-lambda --capabilities CAPABILITY_NAMED_IAM --parameter-overrides KeyBucket=$SCRIPTBUCKET CdnList=$CDNLST AppList=$APPLST
#aws ses verify-email-identity --email-address test@test.com
