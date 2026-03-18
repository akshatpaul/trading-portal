#!/usr/bin/env bash
# ec2.sh — Manually control the trading EC2 instance
# Usage: ./ec2.sh start | stop | status | deploy

INSTANCE_ID="i-02be5abd09ce58873"
REGION="ap-south-1"
PEM="/Users/akshatpaul/myapps/mytrading/trading-key-aws.pem"
EC2_HOST="52.66.125.241"

cmd="${1:-status}"

case "$cmd" in
  start)
    echo "Starting EC2 instance $INSTANCE_ID..."
    aws ec2 start-instances --instance-ids "$INSTANCE_ID" --region "$REGION" --output text --query 'StartingInstances[0].CurrentState.Name'
    echo "Waiting for instance to be running..."
    aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region "$REGION"
    echo "✅ Instance is running — $(date)"
    ;;

  stop)
    echo "Stopping EC2 instance $INSTANCE_ID..."
    aws ec2 stop-instances --instance-ids "$INSTANCE_ID" --region "$REGION" --output text --query 'StoppingInstances[0].CurrentState.Name'
    echo "✅ Stop initiated"
    ;;

  status)
    STATE=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --region "$REGION" \
      --query 'Reservations[0].Instances[0].State.Name' --output text)
    echo "Instance $INSTANCE_ID: $STATE"
    ;;

  deploy)
    echo "Deploying to EC2..."
    ./infra/deploy.sh "$EC2_HOST" "$PEM"
    ;;

  ssh)
    echo "SSHing into EC2..."
    ssh -i "$PEM" ubuntu@"$EC2_HOST"
    ;;

  *)
    echo "Usage: ./ec2.sh start | stop | status | deploy | ssh"
    exit 1
    ;;
esac
