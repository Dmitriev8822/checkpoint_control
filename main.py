import numpy as np
from PyQt5 import uic, QtWidgets
from PyQt5.QtWidgets import QMainWindow, QApplication, QFileDialog, QWidget, QTableWidgetItem
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import QThread, pyqtSignal

import traceback

import cv2
import sys
import queue
import time

from YOLO.yolov8 import main as nn
from db import DatabaseManager

FPS = 120

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
                print(f'Queue size: {self.frame_queue.qsize()}')
                frame = self.frame_queue.get()
                if self.frame_queue.qsize() > 2:
                    self.clear_queue()

                predicts = nn(frame)
                print("Raw list", predicts)
                predicts = list(filter(self.isNormalPlate, predicts))
                predicts.sort(key=lambda predict: -(predict[1][2] - predict[1][0]))
                print("After filter and sort list", predicts)
                predict = "Not recognized"
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
    def __init__(self, blockID, cameraIndex, videoLabel, plateOutLabel):
        # временно и криво
        self.pos = "Въезд" if blockID == 1 else "Выезд"

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

        self.db = DatabaseManager()
        self.connectDB()

    def connectDB(self):
        self.db.connect()
        self.db.create_table()

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
        if result != "Not recognized":
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
                    self.db.add_car(plate, self.pos)
                self.mostPopularPlate = plate
        self.recPlates = list()

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
        self.videoLabel.clear()
        self.videoLabel.setText("Video")


class TableWindow(QWidget):  # Наследуемся от QWidget
    def __init__(self):
        super().__init__()

        uic.loadUi('cars_table.ui', self)

        self.db_manager = DatabaseManager()
        self.data = self.db_manager.get_all_cars()

        self.tableWidget.setRowCount(len(self.data))
        self.tableWidget.setColumnCount(3)
        self.tableWidget.setHorizontalHeaderLabels(["Номер", "Позиция", "Время"])

        # Заполняем таблицу данными
        for row_index, row_data in enumerate(self.data):
            for col_index, value in enumerate(row_data[1:]):
                item = QTableWidgetItem(str(value))
                self.tableWidget.setItem(row_index, col_index, item)

        # Закрываем соединение с БД при закрытии окна
        self.destroyed.connect(self.db_manager.close)


class TestWindow(QWidget):  # Наследуемся от QWidget
    def __init__(self, image):
        super().__init__()

        uic.loadUi('test_window.ui', self)

        frame = image

        height, width, channels = image.shape
        bytes_per_line = channels * width
        q_image = QImage(image.data, width, height, bytes_per_line, QImage.Format_RGB888)

        pixmap = QPixmap.fromImage(q_image)
        self.videoL_1.setPixmap(pixmap7)

        self.nnWorker = NnWorker()
        self.nnWorker.resultsReady.connect(self.handleNnResults)
        self.nnWorker.add_frame(frame)
        self.nnWorker.start()

    def handleNnResults(self, plate: str):
        self.resultPlateOutL_1.setText(plate)
        self.nnWorker.clear_queue()
        self.nnWorker.stop()


    def processFrame(self, image):
        frame = image.convertToFormat(QImage.Format_RGB888)
        width = frame.width()
        height = frame.height()
        ptr = frame.bits()
        ptr.setsize(frame.byteCount())
        frame = np.array(ptr).reshape(height, width, 3)

        # Преобразуем изображение в формат cv2
        frame_cv2 = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        return frame_cv2




class Ui(QMainWindow):
    def __init__(self):
        super(Ui, self).__init__()
        self.ui()

    def ui(self):
        uic.loadUi('main.ui', self)  # Load the .ui file
        self.comboBoxes = [self.cameraNameCB_1, self.cameraNameCB_2]
        self.fillAvailableCameras([self.cameraNameCB_1, self.cameraNameCB_2])

        self.cameraNameCB_1.currentIndexChanged.connect(self.runCamera)
        self.cameraNameCB_2.currentIndexChanged.connect(self.runCamera)

        self.action.triggered.connect(self.carsTable)
        self.actionImage.triggered.connect(self.openImage)

        self.activeCameraUnits = list()

        self.show()

    def carsTable(self):
        self.table_window = TableWindow()  # Создаем экземпляр окна с таблицей
        self.table_window.show()

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

    def openImage(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if file_name:
            image = cv2.imread(file_name)
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            self.test_window = TestWindow(image)  # Создаем экземпляр окна с таблицей
            self.test_window.show()



if __name__ == '__main__':
    app = QApplication(sys.argv)  # Create an instance of QtWidgets.QApplication
    window = Ui()  # Create an instance of our class
    app.exec_()  # Start the application
