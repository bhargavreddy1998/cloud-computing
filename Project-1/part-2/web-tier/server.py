import boto3
import time
import threading
from threading import Thread
from flask import Flask, request, jsonify
from controller import autoscale_loop
app = Flask(__name__)

AWS_ACCESS_KEY_ID = ''
AWS_SECRET_ACCESS_KEY = ''
ASU_ID = "1226491476"
REQUEST_QUEUE_NAME = f"{ASU_ID}-req-queue"
RESPONSE_QUEUE_NAME = f"{ASU_ID}-resp-queue"
S3_BUCKET_NAME = f"{ASU_ID}-in-bucket"

sqs_client = boto3.client('sqs', region_name='us-east-1', aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
ec2_client = boto3.client('ec2', region_name='us-east-1', aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
s3_client = boto3.client("s3", region_name='us-east-1', aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

request_queue_url = sqs_client.get_queue_url(QueueName=REQUEST_QUEUE_NAME)['QueueUrl']
response_queue_url = sqs_client.get_queue_url(QueueName=RESPONSE_QUEUE_NAME)['QueueUrl']

result_map = {}
lock = threading.Lock()

def start_response_polling_thread():
    while True:
        try:
            messages = sqs_client.receive_message(QueueUrl=response_queue_url,MaxNumberOfMessages=10, WaitTimeSeconds=1).get('Messages', [])
            for message in messages:
                msg_body = message['Body']
                file_name = msg_body.split(":", 1)[0]
                face_reg_result = msg_body.split(":", 1)[1]
                with lock:
                    result_map[file_name] = face_reg_result
                sqs_client.delete_message(QueueUrl=response_queue_url,ReceiptHandle=message['ReceiptHandle'])
        except Exception as e:
            print(f"Error in response polling thread: {e}")

@app.route("/", methods=["POST"])
def handle_image_upload():
    try:
        file_obj = request.files['inputFile']
        file_name = file_obj.filename
        filename_no_ext = file_name.split(".")[0]
        s3_client.upload_fileobj(file_obj, S3_BUCKET_NAME, file_name)
        sqs_client.send_message(QueueUrl=request_queue_url, MessageBody=file_name)
        while file_name not in result_map:
            time.sleep(0.1)
        result = result_map.pop(file_name)
        return f"{filename_no_ext}:{result}\n", 200
    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    Thread(target=start_response_polling_thread, daemon=True).start()
    Thread(target=autoscale_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=8000)