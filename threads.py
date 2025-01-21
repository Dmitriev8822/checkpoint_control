import numpy as np
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QDialogButtonBox, QMessageBox
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import QThread, pyqtSignal

import traceback

import cv2
import sys
import queue
import time

from YOLO.yolov8 import main as nn
from db import Database

FPS = 120

def excepthook(exc_type, exc_value, exc_tb):
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    print("Oбнаружена ошибка !:", tb)
    QtWidgets.QApplication.quit()


sys.excepthook = excepthook

class NnWorker(QThread):
    resultsReady = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.frame_queue = queue.Queue()
        self.running = True

    def add_frame(self, frame):
        self.frame_queue.put(frame)

    def clear_queue(self):
        with self.frame_queue.mutex:
            self.frame_queue.queue.clear()

    def run(self):
        while self.running:
            if not self.frame_queue.empty():
                print(f'Queue size: {self.frame_queue.qsize()}')
                frame = self.frame_queue.get()
                if self.frame_queue.qsize() > 2:
                    self.clear_queue()

                predicts = nn(frame)
                print("Raw list", predicts)
                predicts = list(filter(self.isNormalPlate, predicts))
                predicts.sort(key=lambda predict: -(predict[1][2] - predict[1][0]))
                print("After filter and sort list", predicts)
                predict = "Не распознан"
                if predicts != list():
                    predict = predicts[0][0]

                self.resultsReady.emit(predict)

    def isNormalPlate(self, predict: tuple) -> bool:
        import re
        plate = predict[0]
        pattern = r'^[A-Za-z]\d{3}[A-Za-z]{2}\d{2}\d?$'
        return bool(re.match(pattern, plate))

    def stop(self):
        self.running = False
        self.quit()
        self.wait()


class CameraThread(QThread):
    # Сигнал для передачи кадра в основное приложение
    frameSignal = pyqtSignal(QImage)

    def __init__(self, cameraIndex):
        super().__init__()

        self.cap = cv2.VideoCapture(cameraIndex)
        self.timer = QTimer()
        self.timer.timeout.connect(self.updateFrame)
        self.fps = 1000 // FPS
        self.timer.start(self.fps)

    def updateFrame(self):
        ret, frame = self.cap.read()
        if ret:
            # Конвертируем кадр в формат QImage
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            self.frameSignal.emit(qt_image)

    def stop(self):
        self.timer.stop()
        self.cap.release()
        self.quit()
        self.wait()


class CameraUnit:
    def __init__(self, blockID, cameraIndex, videoLabel, plateOutLabel, cameraPosition):
        self.pos = cameraPosition

        self.blockID = blockID
        self.cameraIndex = cameraIndex
        self.videoLabel = videoLabel
        self.plateOutLabel = plateOutLabel
        self.frameCount = 0

        self.timeStart = int(time.time()) % 100
        self.countFPS = 0

        self.nnWorker = NnWorker()
        self.nnWorker.resultsReady.connect(self.handleNnResults)
        self.nnWorker.start()

        self.cameraTheard = None

        self.mostPopularPlate = None
        self.recPlates = list()
        self.recPlatesCntEmpty = 0

        self.testMode = False

        self.db = None
        if not self.testMode:
            self.db = Database()
            self.connectDB()

    def connectDB(self):
        self.db.create_tables()

    def runCamera(self):
        self.cameraTheard = CameraThread(self.cameraIndex)
        self.cameraTheard.frameSignal.connect(self.updateFrame)
        self.cameraTheard.start()

    def countFrames(self) -> None:
        if (int(time.time()) % 100) != self.timeStart:
            self.timeStart = int(time.time()) % 100
            print(f'FPS: {self.countFPS}')
            self.countFPS = 0
        self.countFPS += 1

    def updateFrame(self, image):
        self.countFrames()
        frame = QPixmap.fromImage(image)
        self.videoLabel.setPixmap(frame)
        self.frameCount += 1

        if self.frameCount % 10 == 0:
            self.processFrame(image)

    def processFrame(self, image):
        frame = image.convertToFormat(QImage.Format_RGB888)
        width = frame.width()
        height = frame.height()
        ptr = frame.bits()
        ptr.setsize(frame.byteCount())
        frame = np.array(ptr).reshape(height, width, 3)

        # Преобразуем изображение в формат cv2
        frame_cv2 = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        self.nnWorker.add_frame(frame_cv2)

    def handleNnResults(self, result: str) -> None:
        if result != "Номер не был распознан":
            self.recPlates.append(result)
            if len(self.recPlates) > 10:
                self.getMostPopularPlate()
                self.plateOutLabel.setText(self.mostPopularPlate)

    def getMostPopularPlate(self) -> None:
        if self.recPlates.count(self.mostPopularPlate) > 0:
            self.recPlates.extend([self.mostPopularPlate] * int(len(self.recPlates) * 0.5))

        for plate in self.recPlates:
            lPlateCnt = self.recPlates.count(plate)
            if lPlateCnt >= int(len(self.recPlates) * 0.6):
                if self.mostPopularPlate != plate:
                    self.mostPopularPlate = plate
                    if (not self.testMode) and plate != "Не распознан" and self.checkAccess(plate):
                        self.db.add_car(plate, self.pos)
                        # команда на открытие шлагбаума / ворот

        self.recPlates = list()

    def checkAccess(self, plate):
        if self.db.find_employee(plate):
            return True

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Question)
        msg.setText(f"Автомобиль с номером <{plate}> не найден в базе данных сотрудников.\nПропустить автомобиль?")
        msg.setWindowTitle("Неизвестный автомобиль")
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        retval = msg.exec_()

        return retval == QMessageBox.Ok

    def stopCamera(self):
        if self.cameraTheard is not None:
            self.cameraTheard.stop()
            self.cameraTheard = None

        if self.nnWorker is not None:
            self.nnWorker.clear_queue()
            self.nnWorker.stop()
            self.nnWorker = None

        self.db.close()

        self.plateOutLabel.clear()
        self.plateOutLabel.setText('Номер')
        self.videoLabel.clear()

        image_path = r"C:\Users\racco\Downloads\cameraPicS.jpg"  # Укажите реальный путь
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            self.videoLabel.setPixmap(pixmap)
        else:
            self.videoLabel.setText("Не удалось загрузить изображение")


