#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os

sys.path.append(os.getcwd())
from PIL import Image, ImageDraw, ImageFont
from LPRN.model.LPRNET import LPRNet, CHARS
from LPRN.model.STN import STNet
import numpy as np
import argparse
import torch
import time
import cv2


def convert_image(inp):
    # convert a Tensor to numpy image
    inp = inp.squeeze(0).cpu()
    inp = inp.detach().numpy().transpose((1, 2, 0))
    inp = 127.5 + inp / 0.0078125
    inp = inp.astype('uint8')

    return inp


def decode(preds, CHARS):
    # greedy decode
    pred_labels = list()
    labels = list()
    for i in range(preds.shape[0]):
        pred = preds[i, :, :]
        pred_label = list()
        for j in range(pred.shape[1]):
            pred_label.append(np.argmax(pred[:, j], axis=0))
        no_repeat_blank_label = list()
        pre_c = pred_label[0]
        for c in pred_label:  # dropout repeate label and blank label
            if (pre_c == c) or (c == len(CHARS) - 1):
                if c == len(CHARS) - 1:
                    pre_c = c
                continue
            no_repeat_blank_label.append(c)
            pre_c = c
        pred_labels.append(no_repeat_blank_label)

    for i, label in enumerate(pred_labels):
        lb = ""
        for i in label:
            lb += CHARS[i]
        labels.append(lb)

    return labels, np.array(pred_labels)


def main(image):
    # path = r'C:\Users\Dima\Documents\permanent_folder\TEMP{:04d}.jpg'.format(cnt)
    # parser = argparse.ArgumentParser(description='LPR Demo')
    # parser.add_argument("-image", help='image path', default=path,
    #                     type=str)
    # args = parser.parse_args()

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    lprnet = LPRNet(class_num=len(CHARS), dropout_rate=0)
    lprnet.to(device)
    lprnet.load_state_dict(torch.load('LPRN/weights/LPRNet_real_images.pth', map_location=lambda storage, loc: storage))
    lprnet.eval()

    STN = STNet()
    STN.to(device)
    STN.load_state_dict(torch.load('LPRN/weights/STN_real_images.pth', map_location=lambda storage, loc: storage))
    STN.eval()

    # print("Successful to build network!")

    since = time.time()
    # image = cv2.imread(args.image)
    im = cv2.resize(image, (94, 24), interpolation=cv2.INTER_CUBIC)
    im = (np.transpose(np.float32(im), (2, 0, 1)) - 127.5) * 0.0078125
    data = torch.from_numpy(im).float().unsqueeze(0).to(device)  # torch.Size([1, 3, 24, 94]) 
    transfer = STN(data)
    preds = lprnet(transfer)
    preds = preds.cpu().detach().numpy()  # (1, 68, 18)

    # transformed_img = convert_image(transfer)
    # path_to_redsave = r'C:\Users\Dima\Documents\permanent_folder\red_img_{:04d}.jpg'.format(cnt)
    # cv2.imwrite(path_to_redsave, transformed_img)

    labels, pred_labels = decode(preds, CHARS)
    return labels[0]


if __name__ == '__main__':
    main()
