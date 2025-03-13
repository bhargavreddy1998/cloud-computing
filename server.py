import time
import boto3
import json
from flask import Flask, request
from threading import Thread
from controller import auto_scaling

app = Flask(__name__)

ASU_ID = "1226491476"
S3_BUCKET_NAME = f"{ASU_ID}-in-bucket"
SQS_REQ_QUEUE_NAME = f"{ASU_ID}-req-queue"
SQS_RESP_QUEUE_NAME = f"{ASU_ID}-resp-queue"
REGION = 'us-east-1' 

s3_client = boto3.client("s3", region_name=REGION)
sqs_resource = boto3.resource("sqs", region_name=REGION)
sqs_client = boto3.client("sqs", region_name=REGION)
sqs_req_queue = sqs_resource.get_queue_by_name(QueueName=SQS_REQ_QUEUE_NAME)
sqs_resp_queue = sqs_resource.get_queue_by_name(QueueName=SQS_RESP_QUEUE_NAME)

face_reg_dict = dict()

def send_filename_req_queue(filename):
    message_body = json.dumps({"filename": filename})
    sqs_req_queue.send_message( MessageBody=message_body)
    # print(f"Sent {filename} to request queue")

def store_image_in_s3(file_obj, filename):
    s3_client.upload_fileobj(file_obj, S3_BUCKET_NAME, filename)
    # print(f"Uploaded {filename} to S3 bucket")

def get_result_resp_queue():
    while True:
        response = sqs_client.receive_message(QueueUrl=sqs_resp_queue.url, MaxNumberOfMessages=10, WaitTimeSeconds=10)
        messages = response.get('Messages', [])
        for message in messages:
            try:
                msg_body = json.loads(message['Body'])
                # print(f"Received message: {msg_body}")
                filename = msg_body["filename"]
                # print(f"Received result for {filename}")
                # print(f"Result: {msg_body['result'].strip()}")
                face_reg_dict[filename.split('.')[0]] = msg_body["result"].strip() 
                sqs_client.delete_message(QueueUrl=sqs_resp_queue.url, ReceiptHandle=message['ReceiptHandle'])
                # print(face_reg_dict)
            except Exception as e:
                print(f"Error processing message: {e}")

@app.route("/", methods=["POST"])
def handle_post():
    if "inputFile" not in request.files:
        return "Error: No 'inputFile' key in request.\n", 400
    file_obj = request.files["inputFile"]
    filename = file_obj.filename
    filename_no_ext = filename.split(".")[0]
    try:
        send_filename_req_queue(filename=filename)
        store_image_in_s3(file_obj=file_obj, filename=filename)
        # print(filename_no_ext in face_reg_dict)
        for _ in range(10):
            if filename_no_ext in face_reg_dict:
                return f"{filename}:{face_reg_dict.pop(filename_no_ext)}\n", 200
            time.sleep(1)
        return "File processed\n", 200
    except Exception as e:
        return f"Error processing the request: {str(e)}\n", 500

if __name__ == "__main__":
    Thread(target=get_result_resp_queue, daemon=True).start()
    Thread(target=auto_scaling, daemon=True).start()
    app.run(host="0.0.0.0", port=8000)
