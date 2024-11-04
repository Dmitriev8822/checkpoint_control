import os
from ultralytics import YOLO
import cv2
import numpy as np
from time import time

from LPRN.LPRNet_main import main as lpr

# image_path = os.path.join('..', 'images', '1.jpg')
model_path = os.path.join('YOLO', 'yolov8t4.pt')
model = YOLO(model_path)


def main(image):
    predicts = list()
    ts = time()

    threshold = 0.5

    results = model(image)[0]

    for cnt, result in enumerate(results.boxes.data.tolist()):
        x1, y1, x2, y2, score, class_id = result
        if score > threshold:
            lpr_image = image[int(y1):int(y2), int(x1):int(x2)]
            lpr_image = cv2.resize(lpr_image, (94, 24))

            ts = time()
            predict = str(lpr(lpr_image))
            resultPredict = (predict, (x1, y1, x2, y2))
            predicts.append(resultPredict)
            tf = time()
            print('predict:', predict)
            print(f'Image processed {round(tf - ts, 2)} sec. (LPRNet)')

    tf = time()
    print(f'Image processed {round(tf - ts, 2)} sec. (YOLO)')

    return predicts


if __name__ == '__main__':
    image_path = os.path.join('..', 'images', '1.jpg')
    image = cv2.imread(image_path)
    main(image)
