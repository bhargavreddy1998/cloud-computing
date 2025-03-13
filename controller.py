import boto3
import time
import logging

# AWS credentials and region
AWS_ACCESS_KEY = 'AKIA2ZIONKBBLZXMYLOG'
AWS_SECRET_KEY = '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'
REGION = 'us-east-1'
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# SQS queue names
REQUEST_QUEUE = 'https://sqs.us-east-1.amazonaws.com/741448962114/1226491476-req-queue'

# EC2 instance settings
APP_TIER_INSTANCE_TYPE = 't2.micro'
APP_TIER_AMI_ID = 'ami-04b4f1a9cf54c11d0'
MAX_INSTANCES = 15

# Initialize AWS clients
sqs = boto3.client('sqs', aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_KEY, region_name=REGION)
ec2 = boto3.client('ec2', aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_KEY, region_name=REGION)

def get_pending_messages():
    """Get the number of pending messages in the SQS request queue."""
    response = sqs.get_queue_attributes(QueueUrl=REQUEST_QUEUE, AttributeNames=['ApproximateNumberOfMessages'])
    return int(response['Attributes']['ApproximateNumberOfMessages'])

def get_stopped_instance_ids():
    """Get the IDs of stopped app-tier instances."""
    response = ec2.describe_instances(Filters=[
        {'Name': 'instance-state-name', 'Values': ['stopped']},
        {'Name': 'tag:Name', 'Values': ['app-tier-instance-*']}
    ])
    instance_ids = []
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_ids.append(instance['InstanceId'])
    return instance_ids

def start_instances(instance_ids):
    """Start the specified instances."""
    if instance_ids:
        ec2.start_instances(InstanceIds=instance_ids)
        logging.info(f"Started instances: {instance_ids}")

def stop_instances(instance_ids):
    """Stop the specified instances."""
    if instance_ids:
        ec2.stop_instances(InstanceIds=instance_ids)
        logging.info(f"Stopped instances: {instance_ids}")

def main():
    """Main loop to monitor the SQS queue and scale instances."""
    while True:
        try:
            # Get the number of pending messages
            pending_messages = get_pending_messages()
            logging.info(f"Pending messages: {pending_messages}")

            # Calculate the desired number of instances
            desired_instances = min(pending_messages, MAX_INSTANCES)
            logging.info(f"Desired instances: {desired_instances}")

            # Get the current number of running instances
            running_instances = ec2.describe_instances(Filters=[
                {'Name': 'instance-state-name', 'Values': ['running', 'pending']},
                {'Name': 'tag:Name', 'Values': ['app-tier-instance-*']}
            ])
            running_count = len(running_instances['Reservations'])

            # Start or stop instances as needed
            if desired_instances > running_count:
                stopped_instance_ids = get_stopped_instance_ids()
                num_to_start = min(desired_instances - running_count, len(stopped_instance_ids))
                start_instances(stopped_instance_ids[:num_to_start])
            elif desired_instances < running_count:
                running_instance_ids = [instance['InstanceId'] for reservation in running_instances['Reservations'] for instance in reservation['Instances']]
                num_to_stop = running_count - desired_instances
                stop_instances(running_instance_ids[:num_to_stop])

            # Wait before checking again
            time.sleep(10)
        except Exception as e:
            logging.error(f"Error in main loop: {e}")

if __name__ == '__main__':
    main()
