import os
import json
import boto3
import torch
import numpy as np
from PIL import Image
import io
import base64
from facenet_pytorch import InceptionResnetV1


sqs = boto3.client('sqs')
RESPONSE_QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/879381261134/1226491476-resp-queue'
resnet = InceptionResnetV1(pretrained='vggface2').eval()
saved_data = torch.load("/var/task/resnetV1_video_weights.pt")
embedding_list = saved_data[0]
name_list = saved_data[1]

def lambda_handler(event, context):
    try:
        for record in event['Records']:
            body = json.loads(record['body'])
            request_id = body['request_id']
            face_image = base64.b64decode(body["face_image"])
            face_pil = Image.open(io.BytesIO(face_image)).convert("RGB")
            face_numpy = np.array(face_pil, dtype=np.float32)
            face_numpy /= 255.0
            face_numpy = np.transpose(face_numpy, (2, 0, 1))
            face_tensor = torch.tensor(face_numpy, dtype=torch.float32)
            if face_tensor != None:
                emb = resnet(face_tensor.unsqueeze(0)).detach()
                dist_list = []
                for idx, emb_db in enumerate(embedding_list):
                    dist = torch.dist(emb, emb_db).item()
                    dist_list.append(dist)
                idx_min = dist_list.index(min(dist_list))
                result = name_list[idx_min]
            else:
                print(f"No face is detected")
            try:
                result_body = {"request_id": request_id, "result": result}
                sqs.send_message(QueueUrl=RESPONSE_QUEUE_URL, MessageBody=json.dumps(result_body))
                return {"statusCode": 200,"body": json.dumps(result_body)}
            except Exception as e:
               return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}
    except Exception as e:
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}