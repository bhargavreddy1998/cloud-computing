import boto3

REGION = "us-east-1"

ASU_ID = "1226491476" 
REQUEST_QUEUE_NAME = f"{ASU_ID}-req-queue"

MAX_INSTANCES = 15
AWS_ACCESS_KEY_ID = ""
AWS_SECRET_ACCESS_KEY = ""

sqs_client = boto3.client("sqs", region_name=REGION, aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
ec2_client = boto3.client("ec2", region_name=REGION, aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

request_queue_url = sqs_client.get_queue_url(QueueName=REQUEST_QUEUE_NAME)['QueueUrl']

def get_queue_size():
    resp = sqs_client.get_queue_attributes(QueueUrl=request_queue_url, AttributeNames=["ApproximateNumberOfMessages"])
    return int(resp["Attributes"].get("ApproximateNumberOfMessages", 0))

def get_running_instances():
    response = ec2_client.describe_instances(
        Filters=[
            {"Name": "instance-state-name", "Values": ["running", "pending"]},
            {"Name": "tag:Name", "Values": ["app-tier-instance-*"]}
        ]
    )
    instance_ids = []
    for reservation in response["Reservations"]:
        for instance in reservation["Instances"]:
            instance_ids.append(instance["InstanceId"])
    return instance_ids

def get_stopped_instances():
    response = ec2_client.describe_instances(
        Filters=[
            {"Name": "instance-state-name", "Values": ["stopped", "stopping"]},
            {"Name": "tag:Name", "Values": ["app-tier-instance-*"]}
        ]
    )
    instance_ids = []
    for reservation in response["Reservations"]:
        for instance in reservation["Instances"]:
            instance_ids.append(instance["InstanceId"])
    return instance_ids

def start_instances(count, stopped_list):
    ec2_client.start_instances(InstanceIds=stopped_list[:count])

def stop_instances(instancelist):
    runningList = [i for i in instancelist if ec2_client.describe_instances(InstanceIds=[i])['Reservations'][0]['Instances'][0]['State']['Name'] == 'running']
    if runningList:
        ec2_client.stop_instances(InstanceIds=runningList)

def autoscale_loop():
    while True:
        try:
            queue_size = get_queue_size()
            running = get_running_instances()
            stopped = get_stopped_instances()
            running_count = len(running)
            if queue_size == 0 and running_count > 0:
                zero_count = 1
                max_checks = 10
                for _ in range(max_checks):
                    if get_queue_size() == 0:
                        zero_count += 1
                    else:
                        break
                if zero_count == max_checks:
                    stop_instances(running)
            elif 0<queue_size<=10 and running_count<10:
                req = min(queue_size, 10-running_count)
                start_instances(req, stopped)
            elif queue_size > 10 and running_count < MAX_INSTANCES:
                req = min(queue_size, MAX_INSTANCES)
                start_instances(req-running_count, stopped)
        except Exception as e:
            print(f"Autoscaler error: {e}")

if __name__ == "__main__":
    autoscale_loop()
