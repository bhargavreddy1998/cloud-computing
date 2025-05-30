import os
import json
import boto3
import base64
from PIL import Image
import numpy as np
from facenet_pytorch import MTCNN
import io

sqs = boto3.client('sqs')
REQUEST_QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/879381261134/1226491476-req-queue'
mtcnn = MTCNN(image_size=240, margin=0, min_face_size=20) 

def lambda_handler(event, context):
    try:
        body = json.loads(event['body'])
        request_id = body.get('request_id')
        filename = body.get('filename')
        image_content = base64.b64decode(body['content'])
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
            sqs.send_message(QueueUrl=REQUEST_QUEUE_URL, MessageBody=json.dumps({'request_id': request_id, 'face_image': base64.b64encode(buffer.getvalue()).decode("utf-8"), 'filename': key}))
            return {'statusCode': 200, 'body': json.dumps({'request_id': request_id, 'filename': key})}
        else:
            return {'statusCode': 404, 'body': json.dumps({'message': 'No faces detected','request_id': request_id, 'filename': key})}
    except Exception as e:
        return {'statusCode': 500, 'body': json.dumps({'error': str(e),'request_id': request_id})}