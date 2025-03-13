import boto3
import time
import threading

ASU_ID = "1226491476"
REGION = 'us-east-1'
AMI_ID = "ami-096cfbd50c624de78"
INSTANCE_TYPE = "t2.micro"
SECURITY_GROUP_ID = "sg-054472efd7ae91e49"
KEY_NAME = "my-key-pair"
MAX_INSTANCES = 15

sqs_client = boto3.client("sqs", region_name=REGION)
sqs_resource = boto3.resource("sqs", region_name=REGION)
ec2 = boto3.client("ec2", region_name=REGION)

SQS_REQ_QUEUE_NAME = f"{ASU_ID}-req-queue"
sqs_req_queue = sqs_resource.get_queue_by_name(QueueName=SQS_REQ_QUEUE_NAME)

# Global counter to name each instance
instance_counter = 1
counter_lock = threading.Lock()

def get_message_count():
    response = sqs_client.get_queue_attributes(
        QueueUrl=sqs_req_queue.url,
        AttributeNames=['ApproximateNumberOfMessages']
    )
    return int(response['Attributes'].get('ApproximateNumberOfMessages', 0))

def get_running_instances():
    # We look for either running or pending, named app-tier-instance-*
    response = ec2.describe_instances(
        Filters=[
            {'Name': 'instance-state-name', 'Values': ['running','pending']},
            {'Name': 'tag:Name', 'Values': ["app-tier-instance-*"]}
        ]
    )
    instance_ids = []
    for reservation in response['Reservations']:
        for inst in reservation['Instances']:
            instance_ids.append(inst['InstanceId'])
    return instance_ids

def get_stopped_instances():
    # We look for "stopped" specifically, named app-tier-instance-*
    response = ec2.describe_instances(
        Filters=[
            {'Name': 'instance-state-name', 'Values': ['stopped']},
            {'Name': 'tag:Name', 'Values': ["app-tier-instance-*"]}
        ]
    )
    instance_ids = []
    for reservation in response['Reservations']:
        for inst in reservation['Instances']:
            instance_ids.append(inst['InstanceId'])
    return instance_ids

def start_app_tier_instances(count):
    """
    Start 'count' app-tier instances:
      1) Reuse as many stopped instances as possible.
      2) If not enough stopped, launch new ones (each with a unique name).
    """
    if count <= 0:
        return

    stopped_list = get_stopped_instances()
    stopped_count = len(stopped_list)

    if stopped_count == 0:
        # All new
        run_new_instances(count)
    else:
        if stopped_count >= count:
            to_start = stopped_list[:count]
            ec2.start_instances(InstanceIds=to_start)
        else:
            # Start all stopped
            ec2.start_instances(InstanceIds=stopped_list)
            remainder = count - stopped_count
            run_new_instances(remainder)

def run_new_instances(count):
    """
    Launch 'count' brand-new instances, each with a unique Name like 
    'app-tier-instance-<instance#>', and a user data script that runs backend.py.
    """
    global instance_counter

    user_data_script = """#!/bin/bash
cd /home/ubuntu/CSE546-SPRING-2025
python3 backend.py > /home/ubuntu/backend.log 2>&1
"""

    for _ in range(count):
        with counter_lock:
            name_tag = f"app-tier-instance-{instance_counter}"
            instance_counter += 1

        # Launch 1 instance at a time with the unique name
        response = ec2.run_instances(
            ImageId=AMI_ID,
            InstanceType=INSTANCE_TYPE,
            MinCount=1,
            MaxCount=1,
            KeyName=KEY_NAME,
            SecurityGroupIds=[SECURITY_GROUP_ID],
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': [{'Key': 'Name', 'Value': name_tag}]
            }],
            UserData=user_data_script
        )
        # Optionally, capture response['Instances'][0]['InstanceId'] if you want to track them.

def stop_app_tier_instances(instance_ids):
    if not instance_ids:
        return
    ec2.stop_instances(InstanceIds=instance_ids)

def auto_scaling():
    """
    Continuously monitors the queue and scales app-tier up/down 
    so that # running == min(# messages, MAX_INSTANCES).
    """
    while True:
        try:
            msg_count = get_message_count()
            running_ids = get_running_instances()
            running_count = len(running_ids)

            desired_count = min(msg_count, MAX_INSTANCES)

            if desired_count > running_count:
                start_app_tier_instances(desired_count - running_count)

            elif desired_count < running_count:
                to_stop = running_count - desired_count
                stop_app_tier_instances(running_ids[:to_stop])

            time.sleep(3)

        except Exception as e:
            print(f"[auto_scaling] Error: {str(e)}")
            time.sleep(5)
