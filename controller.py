import boto3
from threading import Thread

ASU_ID = "1226491476"
REGION = 'us-east-1'
AMI_ID = "ami-039f4e54cac564526"
INSTANCE_TYPE = "t2.micro"
SECURITY_GROUP = "app-tier-sg"
KEY_NAME = "my-key-pair"
MAX_INSTANCES = 15

sqs_client = boto3.client("sqs", region_name=REGION)
sqs_resource = boto3.resource("sqs", region_name=REGION)
ec2 = boto3.client("ec2", region_name=REGION)

SQS_REQ_QUEUE_NAME = f"{ASU_ID}-req-queue"
sqs_req_queue = sqs_resource.get_queue_by_name(QueueName=SQS_REQ_QUEUE_NAME)

def get_message_count():
    response = sqs_client.get_queue_attributes(QueueUrl=sqs_req_queue.url,AttributeNames=['ApproximateNumberOfMessages'])
    return int(response['Attributes']['ApproximateNumberOfMessages'])

def get_running_instances():
    response = ec2.describe_instances(Filters=[
        {'Name': 'instance-state-name', 'Values': ['running', 'pending']},
        {'Name': 'tag:Name', 'Values': [f"app-tier-instance-*"]}
    ])
    instances = [inst['InstanceId'] for res in response['Reservations'] for inst in res['Instances']]
    return instances

def launch_instance(instance_number):
    instance_name = f"app-tier-instance-{instance_number}"
    ec2.run_instances(ImageId=AMI_ID, InstanceType=INSTANCE_TYPE, MinCount=1, MaxCount=1, KeyName=KEY_NAME, SecurityGroups=[SECURITY_GROUP],
        TagSpecifications=[{
            'ResourceType': 'instance',
            'Tags': [{'Key': 'Name', 'Value': instance_name}]
        }]
    )

def terminate_instance(instance_id):
    ec2.terminate_instances(InstanceIds=[instance_id])

def auto_scaling():
    instance_counter = 0
    while True:
        message_count = get_message_count()
        running_instances = get_running_instances()
        if message_count > 0:
            if len(running_instances) == 0:
                instance_counter += 1
                launch_instance(instance_counter)
            elif len(running_instances) < min(message_count, MAX_INSTANCES):
                instance_counter += 1
                launch_instance()
        elif len(running_instances) > 0:
            terminate_instance(running_instances[0])    