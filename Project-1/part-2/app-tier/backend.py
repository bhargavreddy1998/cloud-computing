import boto3
import time
import subprocess

ASU_ID = "1226491476"
REQUEST_QUEUE_NAME = f"{ASU_ID}-req-queue"
RESPONSE_QUEUE_NAME = f"{ASU_ID}-resp-queue"
S3_IN_BUCKET_NAME = f"{ASU_ID}-in-bucket"
S3_OUT_BUCKET_NAME = f"{ASU_ID}-out-bucket"
s3_client = boto3.client('s3', aws_access_key_id='', aws_secret_access_key='', region_name='us-east-1')
sqs_client = boto3.client('sqs', aws_access_key_id='', aws_secret_access_key='', region_name='us-east-1')
request_queue_url = sqs_client.get_queue_url(QueueName=REQUEST_QUEUE_NAME)['QueueUrl']
response_queue_url = sqs_client.get_queue_url(QueueName=RESPONSE_QUEUE_NAME)['QueueUrl']

def retrieve_sqs_request():
    while True:
        try:
            messages = sqs_client.receive_message(QueueUrl=request_queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=1).get('Messages', [])
            if messages:
                message = messages[0]
                file_name = message['Body']
                filename_no_ext = file_name.split(".")[0]
                result = process_image(file_name)
                s3_client.put_object(Bucket=S3_OUT_BUCKET_NAME, Key=filename_no_ext, Body=result)
                message_body = f"{file_name}:{result}"
                sqs_client.send_message(QueueUrl=response_queue_url, MessageBody=message_body)
                sqs_client.delete_message(QueueUrl=request_queue_url, ReceiptHandle=message['ReceiptHandle'])
            else:
                time.sleep(0.5)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(0.5)

def process_image(file_name):
    try:
        file_path = f"/home/ubuntu/{file_name}"
        s3_client.download_file(S3_IN_BUCKET_NAME, file_name, file_path)
        virtualEnv = "/home/ubuntu/venv/bin/python"
        process = subprocess.Popen(
            [virtualEnv, "/home/ubuntu/CSE546-SPRING-2025/face_recognition.py", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()
        exit_code = process.wait()
        if exit_code == 0:
            face_reg_result = stdout.decode('utf-8')
        else:
            face_reg_result = stdout.decode('utf-8')
            return f"Error: {stderr.decode('utf-8')}"

        return face_reg_result
    except Exception as e:
        print(f"Error processing image: {e}")
        return "Error"

if __name__ == "__main__":
    retrieve_sqs_request()