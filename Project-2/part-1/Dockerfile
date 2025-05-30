FROM public.ecr.aws/lambda/python:3.8

# Copy and install requirements
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Copy model weights
COPY resnetV1_video_weights.pt ${LAMBDA_TASK_ROOT}/
COPY resnetV1.pt ${LAMBDA_TASK_ROOT}/

RUN mkdir -p /tmp/.cache
ENV TORCH_HOME=/tmp/.cache/torch
ENV XDG_CACHE_HOME=/tmp/.cache/torch
COPY resnetV1_video_weights.pt ${LAMBDA_TASK_ROOT}
COPY resnetV1.pt ${LAMBDA_TASK_ROOT}
# Copy Lambda handlers
COPY fd_lambda.py ${LAMBDA_TASK_ROOT}/
COPY fr_lambda.py ${LAMBDA_TASK_ROOT}/

# Default command
CMD ["fd_lambda.lambda_handler"]