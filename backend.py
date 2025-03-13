import json
import boto3
import subprocess
import os
ASU_ID = "1226491476"
SQS_REQ_QUEUE_NAME = f"{ASU_ID}-req-queue"
SQS_RESP_QUEUE_NAME = f"{ASU_ID}-resp-queue"
S3_OUTPUT_BUCKET = f"{ASU_ID}-out-bucket"
S3_INPUT_BUCKET = f"{ASU_ID}-in-bucket"
REGION = 'us-east-1'

sqs_resource = boto3.resource("sqs", region_name=REGION)
sqs_client = boto3.client("sqs", region_name=REGION)
s3_client = boto3.client("s3", region_name=REGION)
sqs_resp_queue = sqs_resource.get_queue_by_name(QueueName=SQS_RESP_QUEUE_NAME)
sqs_req_queue = sqs_resource.get_queue_by_name(QueueName=SQS_REQ_QUEUE_NAME)

def model_inference_face_recognition(file_download_path):
    command = "python3 " + "face_recognition.py" + " " + file_download_path
    print("command is "+command)
    face_reg_result=subprocess.run(command, shell=True, capture_output=True, text=True).stdout
    return face_reg_result

def store_recognition_result(face_reg_result, filename):
    print("filename is")
    print(filename.split(".")[0])
    s3_client.put_object(Bucket=S3_OUTPUT_BUCKET, Key=filename, Body=face_reg_result)

def send_reg_result_resp_queue(face_reg_result, filename):
    message_body = json.dumps({"filename": filename, "result": face_reg_result})
    sqs_resp_queue.send_message( MessageBody=message_body)


def handle_image(filename):
    file_download_path = f'/tmp/{filename}'
    s3_client.download_file(S3_INPUT_BUCKET, filename, file_download_path)
    face_reg_result = model_inference_face_recognition(file_download_path)
    print("face_reg_result is")
    print(face_reg_result)
    filename_no_ext = filename.split(".")[0]
    store_recognition_result(face_reg_result=face_reg_result,filename=filename_no_ext)
    send_reg_result_resp_queue(face_reg_result=face_reg_result,filename=filename)
    os.remove(file_download_path)

def retrieve_sqs_request():
    while True:
        response = sqs_client.receive_message(QueueUrl=sqs_req_queue.url,MaxNumberOfMessages=1, WaitTimeSeconds=5).get('Messages', [])   
        for message in response:
            try:
                print(message)
                msg_body = json.loads(message['Body'])
                print(msg_body)
                filename = msg_body["filename"]
                print(filename)
                handle_image(filename=filename)
                sqs_client.delete_message(QueueUrl=sqs_req_queue.url,ReceiptHandle=message['ReceiptHandle'])
            
            except Exception as e:
                print(f"Error processing message: {e}")

if __name__ == "__main__":
    retrieve_sqs_request()
