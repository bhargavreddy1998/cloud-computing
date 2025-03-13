import boto3
import time
REGION = 'us-east-1' 
INSTANCE_TYPE = 't2.micro'  
AMI_ID = "ami-096cfbd50c624de78"
sqs = boto3.client('sqs', region_name=REGION)
ec2 = boto3.resource('ec2', region_name=REGION)
MAX_INSTANCES = 15
SCALE_OUT_THRESHOLD = 1
MIN_INSTANCES = 0 
COOLDOWN_PERIOD = 45
INSTANCE_ID_COUNTER = 0

def get_app_instances():
    instances = ec2.instances.filter(
        Filters=[
            {'Name': 'tag:Name', 'Values': ['app-tier-instance-*']},
            {'Name': 'instance-state-name', 'Values': ['running', 'pending']}
        ]
    )
    return list(instances)

def get_pending_requests():
    response = sqs.get_queue_attributes(
        QueueUrl='https://sqs.us-east-1.amazonaws.com/741448962114/1226491476-req-queue',
        AttributeNames=['ApproximateNumberOfMessages']
    )
    return int(response['Attributes'].get('ApproximateNumberOfMessages', 0))
def scale_in():
    instances = get_app_instances()
    if len(instances) > MIN_INSTANCES:
        instance_to_terminate = instances[-1]
        instance_name = None
        if instance_to_terminate.tags:
            for tag in instance_to_terminate.tags:
                if tag['Key'] == 'Name':
                    instance_name = tag['Value']
                    break
        instance_to_terminate.terminate()
        print(f"Terminated EC2 instance: {instance_to_terminate.id}, Name: {instance_name or 'N/A'}")

def scale_out():
    global INSTANCE_ID_COUNTER
    INSTANCE_ID_COUNTER += 1

    current_instances = get_app_instances()
    if len(current_instances) < MAX_INSTANCES:
        instance_name = f'app-tier-instance-{INSTANCE_ID_COUNTER}'
        instance = ec2.create_instances(
            ImageId=AMI_ID,
            InstanceType=INSTANCE_TYPE,
            MinCount=1,
            MaxCount=1,
            KeyName='my-key-pair', 
            SecurityGroupIds=['sg-054472efd7ae91e49'],
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': [{'Key': 'Name', 'Value': instance_name}]
            }],
            UserData='''#!/bin/bash
            cd /home/ubuntu/CSE546-SPRING-2025
            python3 backend.py > /home/ubuntu/backend.log 2>&1 &
            '''
        )
        print(f"Launched new instance: {instance[0].id} with name {instance_name}")
def monitor_request_queue():
    global INSTANCE_ID_COUNTER
    global results
    pending_requests_zero_since = None
    while True:
        global INSTANCE_ID_COUNTER
        pending_requests = get_pending_requests()
        current_instance_count = len(get_app_instances())
        upper_limit = min(MAX_INSTANCES,pending_requests)
        if pending_requests > 0:
            pending_requests_zero_since = None
            if pending_requests > SCALE_OUT_THRESHOLD and  INSTANCE_ID_COUNTER < upper_limit:
                scale_out()
            
        else:
            if pending_requests_zero_since is None:
                pending_requests_zero_since = time.time()
            else:
                time_since_zero = time.time() - pending_requests_zero_since
                if time_since_zero >= COOLDOWN_PERIOD:
                    if current_instance_count > MIN_INSTANCES:
                        instances_to_terminate = current_instance_count - MIN_INSTANCES
                        for _ in range(instances_to_terminate):
                            scale_in()
                            time.sleep(2)
                        INSTANCE_ID_COUNTER = 0
                        results = {}
        time.sleep(1)
