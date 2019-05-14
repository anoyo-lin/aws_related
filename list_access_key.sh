for user in $(aws iam list-users --output text --profile $1 | awk '{print $NF}'); do
  aws iam list-access-keys --user $user --output text --profile $1
done
