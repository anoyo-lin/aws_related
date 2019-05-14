#!/bin/bash
aws ec2 describe-security-groups --profile $1 --output text|sed -n 's/\t/|/gp' > sg_dev
sed -i 's/^[^|].*/|&/' sg_dev
sed -i 's/.*[^|]$/&|/' sg_dev
sed -i 's/^|[^|]*|[^|]*|$/& | | | |/' sg_dev
sed -i 's/^|[^|]*|[^|]*|[^|]*|$/& | | |/' sg_dev
sed -i 's/^|[^|]*|[^|]*|[^|]*|[^|]*|$/& | |/' sg_dev
sed -i 's/^|[^|]*|[^|]*|[^|]*|[^|]*|[^|]*|$/& |/' sg_dev
