import json
import base64
import time
import os
import io
import sys
import traceback
import numpy as np
import boto3
from PIL import Image
from awsiot.greengrasscoreipc.clientv2 import GreengrassCoreIPCClientV2
from facenet_pytorch import MTCNN

seen_requests = set()
mtcnn = MTCNN(image_size=240, margin=0, min_face_size=20)
sqs = boto3.client(service_name='sqs',region_name="us-east-1",aws_access_key_id="",aws_secret_access_key="")
REQUEST_QUEUE_URL=""
RESPONSE_QUEUE_URL=""
def handle_requests(event):
    try:
        body=json.loads(event.binary_message.message)
        content=body['encoded']
        request_id=body['request_id']
        filename=body['filename']
        if request_id in seen_requests:
            return 
        seen_requests.add(request_id)
        image_content = base64.b64decode(content)
        img = Image.open(io.BytesIO(image_content)).convert("RGB")
        img = np.array(img)
        img = Image.fromarray(img)

        key = os.path.splitext(os.path.basename(filename))[0].split(".")[0]
        face, prob = mtcnn(img, return_prob=True, save_path=None)

        if face != None:
            face_img = face - face.min()  
            face_img = face_img / face_img.max()  
            face_img = (face_img * 255).byte().permute(1, 2, 0).numpy() 
            face_pil = Image.fromarray(face_img, mode="RGB")
            buffer = io.BytesIO()
            face_pil.save(buffer, format="JPEG")
            sqs.send_message(QueueUrl=REQUEST_QUEUE_URL, MessageBody=json.dumps({'request_id': request_id, 'face_image': base64.b64encode(buffer.getvalue()).decode("utf-8")}))
            return {'statusCode': 200, 'body': json.dumps({'request_id': request_id, 'filename': key})}
        else:
            print(f"No faces detected in image: {filename}")
            sqs.send_message(QueueUrl=RESPONSE_QUEUE_URL, MessageBody=json.dumps({"result": "No-Face", "request_id": request_id, "filename": filename}))
            return {'statusCode': 200, 'body': json.dumps({'message': 'No faces detected','request_id': request_id, 'filename': key})}  
    except Exception as e:
       return {'statusCode': 500, 'body': json.dumps({'error': str(e),'request_id': request_id})}


try:
    ipc_client = GreengrassCoreIPCClientV2()
    _, operation = ipc_client.subscribe_to_topic(topic='clients/1226491476-IoTThing', on_stream_event=handle_requests)
    print('Successfully subscribed to topic: clients/1226491476-IoTThing')
    try:
        while True:
            time.sleep(1)
    except InterruptedError:
        print('Subscribe interrupted.')
    operation.close()
except Exception:
    print('Exception occurred when using IPC.', file=sys.stderr)
    traceback.print_exc()
    exit(1)
