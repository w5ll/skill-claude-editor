# Modelo de detecção de rosto

`face_detection_yunet_2023mar.onnx`: detector de rosto YuNet, do OpenCV Zoo.

- Origem: https://huggingface.co/opencv/face_detection_yunet (o mesmo arquivo do repositório opencv/opencv_zoo).
- Licença: MIT. Autores: Shiqi Yu e colaboradores (projeto libfacedetection).
- SHA-256: 8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4

Usado por `scripts/rosto.py` para saber onde estão os olhos e a boca do Well, e assim
colocar legenda e elementos 3D fora do rosto e fazer o zoom acompanhar o rosto.
