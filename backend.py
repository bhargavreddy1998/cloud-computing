import json
import boto3
import subprocess
ASU_ID = "1226491476"
SQS_REQ_QUEUE_NAME = f"{ASU_ID}-req-queue"
SQS_RESP_QUEUE_NAME = f"{ASU_ID}-resp-queue"
S3_OUTPUT_BUCKET = f"{ASU_ID}-out-bucket"
S3_INPUT_BUCKET = f"{ASU_ID}-in-bucket"
REGION = 'us-east-1'

sqs_client = boto3.resource("sqs", region_name=REGION)
s3_client = boto3.client("s3", region_name=REGION)
sqs_resp_queue = sqs_client.get_queue_by_name(QueueName=SQS_RESP_QUEUE_NAME)
sqs_req_queue = sqs_client.get_queue_by_name(QueueName=SQS_REQ_QUEUE_NAME)

file_download_path = "/home/bhargav/Downloads/Project1-1226491476-1/CSE546-SPRING-2025/"
face_recognition_path = "/home/bhargav/Downloads/Project1-1226491476-1/CSE546-SPRING-2025/face_recognition.py" 

def model_inference_face_recognition():
    command = "python3 " + face_recognition_path + " " + file_download_path
    face_reg_result=subprocess.run(command, shell=True, capture_output=True, text=True)
    return face_reg_result

def store_recognition_result(face_reg_result, filename):
    s3_client.upload_fileobj(face_reg_result, S3_OUTPUT_BUCKET, filename)

def send_reg_result_resp_queue(face_reg_result, filename):
    message_body = json.dumps({"filename": filename, "result": face_reg_result})
    sqs_resp_queue.send_message( MessageBody=message_body)


def handle_image(filename):
    s3_client.download_file(S3_INPUT_BUCKET, filename, file_download_path)
    face_reg_result = model_inference_face_recognition()
    store_recognition_result(face_reg_result=face_reg_result,filename=filename)
    send_reg_result_resp_queue(face_reg_result=face_reg_result,filename=filename)

def retrieve_sqs_request():
    while True:
        response = sqs_req_queue.receive_messages(MaxNumberOfMessages=1, WaitTimeSeconds=5)        
        if 'Messages' in response:
            for message in response['Messages']:
                try:
                    msg_body = json.loads(message['Body'])
                    filename = msg_body["filename"]
                    handle_image(filename=filename)
                    sqs_resp_queue.delete_message(ReceiptHandle=message['ReceiptHandle'])
                
                except Exception as e:
                    print(f"Error processing message: {e}")

if __name__ == "__main__":
    retrieve_sqs_request()
