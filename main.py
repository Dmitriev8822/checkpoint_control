import numpy as np
from PyQt5 import uic, QtWidgets
from PyQt5.QtWidgets import QMainWindow, QApplication, QFileDialog, QWidget, QTableWidgetItem, QVBoxLayout, QLabel, \
    QHBoxLayout, QComboBox
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import QThread, pyqtSignal

import traceback

import cv2
import sys
import queue
import time

from db import DatabaseManager
from threads import CameraUnit, NnWorker

blockIndex = 2


def excepthook(exc_type, exc_value, exc_tb):
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    print("Oбнаружена ошибка !:", tb)
    QtWidgets.QApplication.quit()


sys.excepthook = excepthook


def logAction():
    pass


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
        self.videoL_1.setPixmap(pixmap)

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


class Ui2(QMainWindow):
    def __init__(self):
        super(Ui2, self).__init__()
        self.ui()

    def ui(self):
        uic.loadUi('main3.ui', self)  # Load the .ui file
        # self.fillAvailableCameras([self.cameraNameCB_1, self.cameraNameCB_2])

        # self.cameraNameCB_1.currentIndexChanged.connect(self.runCamera)
        # self.cameraNameCB_2.currentIndexChanged.connect(self.runCamera)

        self.A_notes.triggered.connect(self.carsTable)
        self.A_photo.triggered.connect(self.openImage)
        self.A_add.triggered.connect(self.addCameraBlock)
        self.A_update.triggered.connect(self.fillAvailableCameras)

        self.activeCameraUnits = list()

        self.show()

    def addCameraBlock(self) -> None:
        global blockIndex

        # создание расположений (layout)
        VL_cameraBlock = QVBoxLayout()
        VL_cameraBlock.setObjectName(f'VL_cameraBlock_{blockIndex}')

        HL_cameraPosition = QHBoxLayout()
        HL_cameraPosition.setObjectName(f'HL_cameraPosition_{blockIndex}')

        HL_cameraIndex = QHBoxLayout()
        HL_cameraIndex.setObjectName(f'HL_cameraIndex_{blockIndex}')

        HL_cameraName = QHBoxLayout()
        HL_cameraName.setObjectName(f'HL_cameraName_{blockIndex}')

        # создание меток (label)
        L_cameraName = QLabel(f'Камера №{blockIndex}')
        L_cameraName.setObjectName(f'L_cameraName_{blockIndex}')

        L_resultPlateOut = QLabel("Номер")
        L_resultPlateOut.setObjectName(f'L_resultPlateOut_{blockIndex}')

        L_videoOut = QLabel("Видео")
        L_videoOut.setObjectName(f'L_videoOut_{blockIndex}')

        L_cameraPosition = QLabel("Расположение:")
        L_cameraPosition.setObjectName(f'L_cameraPosition_{blockIndex}')

        L_cameraIndex = QLabel("Камера:")
        L_cameraIndex.setObjectName(f'L_cameraIndex_{blockIndex}')

        # создание выпадающих списков (combo box)
        CB_cameraPosition = QComboBox()
        CB_cameraPosition.setObjectName(f'CB_cameraPosition_{blockIndex}')
        CB_cameraPosition.addItem('')
        CB_cameraPosition.addItem('Въезд')
        CB_cameraPosition.addItem('Выезд')

        CB_cameraIndex = QComboBox()
        CB_cameraIndex.setObjectName(f'CB_cameraIndex_{blockIndex}')

        # добавление всех элементов
        self.HL_mainLayout.addLayout(VL_cameraBlock)

        VL_cameraBlock.addWidget(L_cameraName)
        VL_cameraBlock.addLayout(HL_cameraPosition)
        VL_cameraBlock.addLayout(HL_cameraIndex)
        VL_cameraBlock.addWidget(L_resultPlateOut)
        VL_cameraBlock.addWidget(L_videoOut)

        HL_cameraPosition.addWidget(L_cameraPosition)
        HL_cameraPosition.addWidget(CB_cameraPosition)

        HL_cameraIndex.addWidget(L_cameraIndex)
        HL_cameraIndex.addWidget(CB_cameraIndex)

        # VL_cameraBlock.setStretch()

        # увеличение индекса (для создания корректных id новых блоков)
        blockIndex += 1

        CB_cameraIndex.currentIndexChanged.connect(self.runCamera)

    def updateCameraBlock(self) -> None:
        pass

    def deleteCameraBlock(self) -> None:
        pass

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
            return -1

        videoLabel = self.findChild(QtWidgets.QLabel, f'L_videoOut_{blockID}')
        plateOutLabel = self.findChild(QtWidgets.QLabel, f'L_resultPlateOut_{blockID}')
        cameraPosition = self.findChild(QtWidgets.QComboBox, f'CB_cameraPosition_{blockID}').currentIndex() - 1
        cameraUnit = CameraUnit(blockID, cameraIndex, videoLabel, plateOutLabel, cameraPosition)
        cameraUnit.runCamera()
        self.activeCameraUnits.append(cameraUnit)

        return 0

    def fillAvailableCameras(self) -> None:
        comboBoxes = [self.findChild(QtWidgets.QComboBox, f'CB_cameraIndex_{bi}') for bi in range(2, blockIndex)]
        for cameraBox in comboBoxes:
            cameraBox.clear()
            cameraBox.addItem("")

        availableCameras = self.getAvailableCameras()

        for cameraIndex in availableCameras:
            for cameraBox in comboBoxes:
                cameraBox.addItem("Камера " + str(cameraIndex))

    def getAvailableCameras(self, maxCameras=10) -> list:
        availableCameras = list()
        for index in range(maxCameras):
            cap = cv2.VideoCapture(index)
            if cap.isOpened():
                availableCameras.append(index)
                cap.release()  # Закрываем камеру после проверки

        return availableCameras

    def openImage(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if file_name:
            image = cv2.imread(file_name)
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            self.test_window = TestWindow(image)  # Создаем экземпляр окна с таблицей
            self.test_window.show()


if __name__ == '__main__':
    app = QApplication(sys.argv)  # Create an instance of QtWidgets.QApplication
    window = Ui2()  # Create an instance of our class
    app.exec_()  # Start the application
