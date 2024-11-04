import numpy as np
from PyQt5 import uic, QtWidgets
from PyQt5.QtWidgets import QMainWindow, QApplication, QFileDialog
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import QThread, pyqtSignal

import traceback

import cv2
import sys
import queue

from YOLO.yolov8 import main as nn

FPS = 30

frame_processing_time = list()


# cnt_frames = 0
# cnt_nn_frames = 0

def excepthook(exc_type, exc_value, exc_tb):
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    print("Oбнаружена ошибка !:", tb)
    QtWidgets.QApplication.quit()


sys.excepthook = excepthook


def logAction():
    pass


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
                frame = self.frame_queue.get()
                predicts = nn(frame)
                print("Raw list", predicts)
                predicts = list(filter(self.isNormalPlate, predicts))
                predicts.sort(key=lambda predict: -(predict[1][2] - predict[1][0]))
                print("After filter and sort list", predicts)
                predict = "Not recognized"
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
    def __init__(self, blockID, cameraIndex, videoLabel, plateOutLabel):
        self.blockID = blockID
        self.cameraIndex = cameraIndex
        self.videoLabel = videoLabel
        self.plateOutLabel = plateOutLabel
        self.frameCount = 0

        self.nnWorker = NnWorker()

        self.cameraTheard = None

    def runCamera(self):
        self.cameraTheard = CameraThread(self.cameraIndex)
        self.cameraTheard.frameSignal.connect(self.updateFrame)
        self.cameraTheard.start()

    def updateFrame(self, image):
        frame = QPixmap.fromImage(image)
        self.videoLabel.setPixmap(frame)
        self.frameCount += 1

        if self.frameCount % 15 == 0:
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
        self.nnWorker.resultsReady.connect(self.handleNnResults)
        self.nnWorker.start()

    def handleNnResults(self, result: str) -> None:
        if result != "Not recognized":
            self.plateOutLabel.setText(result)

    def stopCamera(self):
        if self.cameraTheard is not None:
            self.cameraTheard.stop()
            self.cameraTheard = None


class Ui(QMainWindow):
    def __init__(self):
        super(Ui, self).__init__()

        # self.videoLabels = [self.videoLabel1, self.videoLabel2]
        # self.plateLabels = [self.plateLabel1, self.plateLabel2]
        # self.indexesActiveCameras = dict()

        # self.uiBlocks = list()

        # self.conterFrames = 0
        # self.predicts = []
        # self.availableCameras = list()

        self.ui()

    def ui(self):
        uic.loadUi('main.ui', self)  # Load the .ui file
        self.comboBoxes = [self.cameraNameCB_1, self.cameraNameCB_2]
        self.fillAvailableCameras([self.cameraNameCB_1, self.cameraNameCB_2])

        # self.actionImage.triggered.connect(self.openImage)

        self.cameraNameCB_1.currentIndexChanged.connect(self.runCamera)
        self.cameraNameCB_2.currentIndexChanged.connect(self.runCamera)

        # self.timer.start(fps)

        self.activeCameraUnits = list()

        self.show()

    def runCamera(self) -> int:
        comboBox = self.sender()
        blockID = int(comboBox.objectName().split('_')[-1])

        for cameraUnit in self.activeCameraUnits:
            if cameraUnit.blockID == blockID:
                cameraUnit.stopCamera()
                self.activeCameraUnits.remove(cameraUnit)

        cameraIndex = comboBox.currentIndex() - 1

        if cameraIndex == -1:
            return 0

        videoLabel = self.findChild(QtWidgets.QLabel, f'videoL_{blockID}')
        plateOutLabel = self.findChild(QtWidgets.QLabel, f'resultPlateOutL_{blockID}')
        cameraUnit = CameraUnit(blockID, cameraIndex, videoLabel, plateOutLabel)
        cameraUnit.runCamera()
        self.activeCameraUnits.append(cameraUnit)

        return 0

    def runCameraOld(self):
        comboBox = self.sender()
        videoLabel = self.videoLabels[self.comboBoxes.index(comboBox)]
        videoLabelIndex = self.videoLabels.index(videoLabel)
        cameraIndex = comboBox.currentIndex() - 1

        if videoLabelIndex in self.namesActiveCameras:
            self.indexesActiveCameras[videoLabelIndex].stop()

        if cameraIndex == -1:
            return

        camera = CameraThread(videoLabelIndex, cameraIndex)
        camera.frameSignal.connect(self.updateFrame)
        camera.start()

        self.indexesActiveCameras[videoLabelIndex] = camera

        '''
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            if self.conterFrames % 15 == 0:
                self.nnWorker = NnWorker(frame)
                self.nnWorker.resultsReady.connect(self.on_predicts_ready)
                self.nnWorker.start()

            if self.predicts:
                spliterCoord = self.getSplitCoord(frame)
                self.sortPredicts(spliterCoord) 

            # frame = self.drawPlateNumber(frame)
            self.plateOutput()
            frame = self.drawLine(frame)

            frame = QImage(frame, frame.shape[1], frame.shape[0], QImage.Format_RGB888)
            self.video_label.setPixmap(QPixmap.fromImage(frame))
            self.conterFrames += 1

            # cnt_frames += 1

        # print(cnt_frames, cnt_nn_frames)
        '''

    def updateFrame(self, image):
        videoLabel = self.videoLabels[self.sender().videoLabelIndex]
        frame = QPixmap.fromImage(image)
        videoLabel.setPixmap(frame)
        self.sender().couterFrame += 1

        if self.sender().conterFrames % 15 == 0:
            self.nnWorker = NnWorker(frame)
            self.nnWorker.resultsReady.connect(self.onPredictsReady)
            self.nnWorker.start()

        if self.predicts:
            spliterCoord = self.getSplitCoord(frame)
            self.sortPredicts(spliterCoord)

    def fillAvailableCameras(self, *args) -> None:
        for cameraBox in args[0]:
            cameraBox.clear()
            cameraBox.addItem("")

        self.getAvailableCameras()

        for cameraIndex in self.availableCameras:
            for cameraBox in args[0]:
                cameraBox.addItem("Камера " + str(cameraIndex))

    def getAvailableCameras(self, maxCameras=10) -> None:
        self.availableCameras = list()
        for index in range(maxCameras):
            cap = cv2.VideoCapture(index)
            if cap.isOpened():
                self.availableCameras.append(index)
                cap.release()  # Закрываем камеру после проверки

    def onPredictsReady(self, predicts):
        self.predicts = predicts

    def drawPlateNumber(self, frame):
        height, width, _ = frame.shape
        plateOutHeight = int(height * 0.1)
        plateOutWidth = int(width * 0.5)

        if not (self.lastCarLeft is None):
            cv2.rectangle(frame, (0, 0), (plateOutWidth, plateOutHeight), (0, 0, 0), -1)
            font = cv2.FONT_HERSHEY_SIMPLEX
            cv2.putText(frame, self.lastCarLeft, (int(plateOutWidth * 0.25), int(plateOutHeight * 0.7)), font, 1,
                        (255, 255, 255), 2)

        if not (self.lastCarRight is None):
            cv2.rectangle(frame, (int(width // 2), 0), (plateOutWidth + int(width // 2), plateOutHeight), (0, 0, 0), -1)
            font = cv2.FONT_HERSHEY_SIMPLEX
            cv2.putText(frame, self.lastCarRight, (int(plateOutWidth * 1.25), int(plateOutHeight * 0.7)), font, 1,
                        (255, 255, 255), 2)

        return frame

    def drawLine(self, frame):
        lineCoord = self.lineCoord
        height, width, _ = frame.shape

        x = int(width * lineCoord / 100)

        # Рисуем вертикальную линию от верхней до нижней границы кадра
        start_point = (x, 0)  # Начало линии (сверху от изображения)
        end_point = (x, height)  # Конец линии (снизу от изображения)

        cv2.line(frame, start_point, end_point, (255, 0, 0), 2)

        return frame

    def getSplitCoord(self, frame) -> int:
        height, width, _ = frame.shape
        return int(width * self.lineCoord / 100)

    def plateOutput(self) -> None:
        if not (self.lastCarLeft is None):
            self.plateLabel.setText(self.lastCarLeft)

        if not (self.lastCarRight is None):
            self.plateLabelOut.setText(self.lastCarRight)

    def sortPredicts(self, splitLine) -> None:
        print(self.predicts)
        predictPlateWidthLeft = 0
        predictPlateWidthRight = 0

        for predict in self.predicts:
            plate, coords = predict
            if not self.is_normal_plate(plate):
                continue

            splitter = splitLine
            predictPlateWidth = coords[2] - coords[0]
            if coords[2] < splitter and coords[0] < splitter:
                predictPlateWidthLeft = predictPlateWidth if predictPlateWidth > predictPlateWidthLeft else predictPlateWidthLeft
                self.lastCarLeft = plate
            if coords[2] > splitter and coords[0] > splitter:
                predictPlateWidthRight = predictPlateWidth if predictPlateWidth > predictPlateWidthRight else predictPlateWidthRight
                self.lastCarRight = plate

        if self.lastCarLeft is not None:
            print("lastnCarLeft = ", self.lastCarLeft)

        if self.lastCarRight is not None:
            print("lastnCarRight = ", self.lastCarRight)

        self.predicts = list()

    @staticmethod
    def is_normal_plate(plate: str) -> bool:
        import re
        pattern = r'^[A-Za-z]\d{3}[A-Za-z]{2}\d{2}\d?$'
        return bool(re.match(pattern, plate))

    def openImage(self) -> None:
        self.timer.stop()
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if file_name:
            image = cv2.imread(file_name)
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            self.predicts = nn(image)
            self.sortPredicts(self.getSplitCoord(image))
            self.plateOutput()
            self.drawLine(image)

            image = QImage(image, image.shape[1], image.shape[0], QImage.Format_RGB888)
            self.video_label.setPixmap(QPixmap.fromImage(image))


if __name__ == '__main__':
    app = QApplication(sys.argv)  # Create an instance of QtWidgets.QApplication
    window = Ui()  # Create an instance of our class
    app.exec_()  # Start the application
