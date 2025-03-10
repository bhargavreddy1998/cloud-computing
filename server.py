import boto3
import json
from flask import Flask, request

app = Flask(__name__)

ASU_ID = "1226491476"
S3_BUCKET_NAME = f"{ASU_ID}-in-bucket"
SQS_REQ_QUEUE_NAME = f"{ASU_ID}-req-queue"
SQS_RESP_QUEUE_NAME = f"{ASU_ID}-resp-queue"
REGION = 'us-east-1' 

s3_client = boto3.client("s3", region_name=REGION)
sqs_client = boto3.resource("sqs", region_name=REGION)
sqs_req_queue = sqs_client.get_queue_by_name(QueueName=SQS_REQ_QUEUE_NAME)
sqs_resp_queue = sqs_client.get_queue_by_name(QueueName=SQS_RESP_QUEUE_NAME)

results = []
def send_filename_req_queue(filename):
    message_body = json.dumps({"filename": filename})
    sqs_req_queue.send_message( MessageBody=message_body)

def store_image_in_s3(file_obj, filename):
    s3_client.upload_fileobj(file_obj, S3_BUCKET_NAME, filename)

def get_result_resp_queue():
    while True:
        response = sqs_resp_queue.receive_message(MaxNumberOfMessages=1, WaitTimeSeconds=5)        
        if 'Messages' in response:
            for message in response['Messages']:
                try:
                    msg_body = json.loads(message['Body'])
                    filename = msg_body["filename"]
                    results[filename] = msg_body["result"]
                    sqs_resp_queue.delete_message(ReceiptHandle=message['ReceiptHandle'])
                
                except Exception as e:
                    print(f"Error processing message: {e}")

@app.route("/", methods=["POST"])
def handle_post():
    if "inputFile" not in request.files:
        return "Error: No 'inputFile' key in request.\n", 400
    file_obj = request.files["inputFile"]
    filename = file_obj.filename.split('.')[0]
    try:
        store_image_in_s3(file_obj=file_obj, filename=filename)
        send_filename_req_queue(filename=filename)
        get_result_resp_queue()
        face_reg_result = results[filename]
        return f"{filename}:{face_reg_result}\n", 200
    except Exception as e:
        return f"Error processing the request: {str(e)}\n", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, threaded=True)
