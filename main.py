import numpy as np
from PyQt5 import uic, QtWidgets
from PyQt5.QtWidgets import QMainWindow, QApplication, QFileDialog, QWidget, QTableWidgetItem, QVBoxLayout, QLabel, \
    QHBoxLayout, QComboBox, QMessageBox, QFrame, QSpacerItem, QSizePolicy
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPixmap, QImage, QFont
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtCore import Qt

import traceback

import cv2
import sys
import queue
import time

from db import Database
from threads import CameraUnit, NnWorker

MAXBLOCKINDEX = 0


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

        self.db_manager = Database()
        self.data = self.db_manager.get_all_cars()

        self.tableWidget.setRowCount(len(self.data))
        self.tableWidget.setColumnCount(5)
        self.tableWidget.setHorizontalHeaderLabels(["Номерной знак", "Имя", "Отдел", "Направление", "Дата и время"])

        # Заполняем таблицу данными
        for row_index, row_data in enumerate(self.data):
            for col_index, value in enumerate(row_data):
                if value is None:
                    value = 'Информация отсутствует'
                item = QTableWidgetItem(str(value))
                self.tableWidget.setItem(row_index, col_index, item)

        # Закрываем соединение с БД при закрытии окна
        self.destroyed.connect(self.db_manager.close)


class PhotoTestWin(QWidget):  # Наследуемся от QWidget
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

class VideoTestWin(QWidget):
    def __init__(self, videoPath):
        return -1  # требует доработки
        super().__init__()
        uic.loadUi('test_window.ui', self)

        if not hasattr(self, 'videoL_1') or not hasattr(self, 'resultPlateOutL_1'):
            raise AttributeError("Элементы videoL_1 или resultPlateOutL_1 не найдены в test_window.ui")
        else:
            print("all ok")

        self.show()
        cu = CameraUnit(0, videoPath, self.videoL_1, self.resultPlateOutL_1, 0)  # Инициализация CameraUnit
        cu.testMode = True
        cu.runCamera()



class Ui(QMainWindow):
    def __init__(self):
        super(Ui, self).__init__()
        self.ui()

    def ui(self):
        uic.loadUi('main.ui', self)  # Load the .ui file

        self.A_notes.triggered.connect(self.carsTable)
        self.A_photo.triggered.connect(self.openImage)
        self.A_video.triggered.connect(self.openVideo)
        self.A_add.triggered.connect(self.addCameraBlock)
        self.A_update.triggered.connect(self.fillAvailableCameras)
        self.A_delete.triggered.connect(self.deleteCameraBlock)

        self.activeCameraUnits = list()

        self.show()

        # self.fillAvailableCameras()

        for i in range(2):
            self.addCameraBlock()

    def addCameraBlock(self) -> None:
        global MAXBLOCKINDEX

        # Увеличение индекса (для создания корректных id новых блоков)
        MAXBLOCKINDEX += 1

        # Создаем виджет-блок
        cameraBlockWidget = QWidget()
        cameraBlockWidget.setObjectName(f'cameraBlock_{MAXBLOCKINDEX}')  # Имя для стилей

        # Создаем основной компоновщик для блока
        VL_cameraBlock = QVBoxLayout(cameraBlockWidget)

        # Создание расположений (layout)
        HL_cameraPosition = QHBoxLayout()
        HL_cameraPosition.setObjectName(f'HL_cameraPosition_{MAXBLOCKINDEX}')

        HL_cameraIndex = QHBoxLayout()
        HL_cameraIndex.setObjectName(f'HL_cameraIndex_{MAXBLOCKINDEX}')

        # Создание меток (label)
        L_cameraName = QLabel(f'Камера №{MAXBLOCKINDEX}')
        L_cameraName.setObjectName(f'L_cameraName_{MAXBLOCKINDEX}')
        L_cameraName.setAlignment(Qt.AlignCenter)
        L_cameraName.setFixedHeight(50)

        L_resultPlateOut = QLabel("Номер")
        L_resultPlateOut.setObjectName(f'L_resultPlateOut_{MAXBLOCKINDEX}')
        L_resultPlateOut.setAlignment(Qt.AlignCenter)
        L_resultPlateOut.setFixedHeight(50)

        L_videoOut = QLabel("Видео")
        L_videoOut.setObjectName(f'L_videoOut_{MAXBLOCKINDEX}')
        L_videoOut.setScaledContents(True)

        L_cameraPosition = QLabel("Расположение:")
        L_cameraPosition.setObjectName(f'L_cameraPosition_{MAXBLOCKINDEX}')
        L_cameraPosition.setAlignment(Qt.AlignLeft)

        L_cameraIndex = QLabel("Камера:")
        L_cameraIndex.setObjectName(f'L_cameraIndex_{MAXBLOCKINDEX}')
        L_cameraIndex.setAlignment(Qt.AlignLeft)

        # Создание выпадающих списков (combo box)
        CB_cameraPosition = QComboBox()
        CB_cameraPosition.setObjectName(f'CB_cameraPosition_{MAXBLOCKINDEX}')
        CB_cameraPosition.addItem('')
        CB_cameraPosition.addItem('Въезд')
        CB_cameraPosition.addItem('Выезд')

        CB_cameraIndex = QComboBox()
        CB_cameraIndex.setObjectName(f'CB_cameraIndex_{MAXBLOCKINDEX}')

        line = QFrame(self)
        line.setFrameShape(QFrame.HLine)  # Устанавливаем форму линии (горизонтальная)
        line.setFrameShadow(QFrame.Sunken)

        line2 = QFrame(self)
        line2.setFrameShape(QFrame.HLine)  # Устанавливаем форму линии (горизонтальная)
        line2.setFrameShadow(QFrame.Sunken)

        line3 = QFrame(self)
        line3.setFrameShape(QFrame.HLine)  # Устанавливаем форму линии (горизонтальная)
        line3.setFrameShadow(QFrame.Sunken)

        line4 = QFrame(self)
        line4.setFrameShape(QFrame.HLine)  # Устанавливаем форму линии (горизонтальная)
        line4.setFrameShadow(QFrame.Sunken)

        # Добавление элементов в layouts
        VL_cameraBlock.addWidget(L_cameraName, stretch=1)  # Растяжение для имени камеры
        VL_cameraBlock.addWidget(line)
        VL_cameraBlock.addLayout(HL_cameraPosition, stretch=2)  # Больше места для позиции
        VL_cameraBlock.addWidget(line4)
        VL_cameraBlock.addLayout(HL_cameraIndex, stretch=2)
        VL_cameraBlock.addWidget(line2)
        VL_cameraBlock.addWidget(L_resultPlateOut, stretch=1)  # Меньше места для номера
        VL_cameraBlock.addWidget(line3)
        VL_cameraBlock.addWidget(L_videoOut, stretch=4)  # Видео занимает больше места

        HL_cameraPosition.addWidget(L_cameraPosition)
        HL_cameraPosition.addWidget(CB_cameraPosition)


        HL_cameraIndex.addWidget(L_cameraIndex)
        HL_cameraIndex.addWidget(CB_cameraIndex)

        # Добавляем блок на главную форму
        self.HL_mainLayout.addWidget(cameraBlockWidget)

        # Подключение сигналов
        CB_cameraIndex.currentIndexChanged.connect(self.runCamera)
        # self.fillAvailableCameras()

        cameraBlockWidget.setStyleSheet("""
            QWidget#cameraBlock_""" + str(MAXBLOCKINDEX) + """ {
                font-family: 'Open Sans';
                background-color: lightgray;
                border: 1px solid black;
                border-radius: 15px;
                padding: 10px;
            }
            QLabel#L_resultPlateOut_""" + str(MAXBLOCKINDEX) + """ {
                font-size: 16pt;
                font-style: bold;
            }
            
        """)

        image_path = r"cameraPicS.jpg" # Укажите реальный путь
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            L_videoOut.setPixmap(pixmap)
        else:
            L_videoOut.setText("Не удалось загрузить изображение")


    def updateCameraBlock(self) -> None:
        pass

    def deleteCameraBlock(self) -> None:
        global MAXBLOCKINDEX

        cameraBlock = self.findChild(QtWidgets.QVBoxLayout, f'VL_cameraBlock_{MAXBLOCKINDEX}')
        cameraBlock.deleteLater()

        VL_cameraBlock = self.findChild(QtWidgets.QVBoxLayout, f'VL_cameraBlock_{MAXBLOCKINDEX}')
        HL_cameraPosition = self.findChild(QtWidgets.QHBoxLayout, f'HL_cameraPosition_{MAXBLOCKINDEX}')
        HL_cameraIndex = self.findChild(QtWidgets.QHBoxLayout, f'HL_cameraIndex_{MAXBLOCKINDEX}')

        L_cameraName = self.findChild(QtWidgets.QLabel, f'L_cameraName_{MAXBLOCKINDEX}')
        L_resultPlateOut = self.findChild(QtWidgets.QLabel, f'L_resultPlateOut_{MAXBLOCKINDEX}')
        L_videoOut = self.findChild(QtWidgets.QLabel, f'L_videoOut_{MAXBLOCKINDEX}')
        L_cameraPosition = self.findChild(QtWidgets.QLabel, f'L_cameraPosition_{MAXBLOCKINDEX}')
        L_cameraIndex = self.findChild(QtWidgets.QLabel, f'L_cameraIndex_{MAXBLOCKINDEX}')

        CB_cameraPosition = self.findChild(QtWidgets.QComboBox, f'CB_cameraPosition_{MAXBLOCKINDEX}')
        CB_cameraIndex = self.findChild(QtWidgets.QComboBox, f'CB_cameraIndex_{MAXBLOCKINDEX}')

        # удаление объектов QLabel
        L_cameraName.deleteLater()
        L_resultPlateOut.deleteLater()
        L_videoOut.deleteLater()
        L_cameraPosition.deleteLater()
        L_cameraIndex.deleteLater()

        # Удаление объектов QComboBox
        CB_cameraPosition.deleteLater()
        CB_cameraIndex.deleteLater()

        # Удаление объектов QLayout
        VL_cameraBlock.deleteLater()
        HL_cameraPosition.deleteLater()
        HL_cameraIndex.deleteLater()

        MAXBLOCKINDEX -= 1


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
        cameraPosition = self.findChild(QtWidgets.QComboBox, f'CB_cameraPosition_{blockID}').currentIndex()
        cameraPosition = ['Информация отсутствует', 'Въезд', 'Выезд'][cameraPosition]
        cameraUnit = CameraUnit(blockID, cameraIndex, videoLabel, plateOutLabel, cameraPosition)
        cameraUnit.runCamera()
        self.activeCameraUnits.append(cameraUnit)

        return 0

    def fillAvailableCameras(self) -> None:
        comboBoxes = [self.findChild(QtWidgets.QComboBox, f'CB_cameraIndex_{bi}') for bi in range(1, MAXBLOCKINDEX + 1)]
        for cameraBox in comboBoxes:
            cameraBox.clear()
            cameraBox.addItem("")

        availableCameras = self.getAvailableCameras()

        for cameraIndex in availableCameras:
            for cameraBox in comboBoxes:
                cameraBox.addItem("Камера " + str(cameraIndex))

    def getAvailableCameras(self, maxCameras=2) -> list:
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

            self.test_window = PhotoTestWin(image)  # Создаем экземпляр окна с таблицей
            self.test_window.show()

    def openVideo(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Video", "", "Все файлы (*.*)")
        print(file_path)
        vt = VideoTestWin(file_path)


if __name__ == '__main__':
    app = QApplication(sys.argv)  # Create an instance of QtWidgets.QApplication
    default_font = QFont("Open Sans", 14)  # Шрифт Open Sans, размер 12
    app.setFont(default_font)
    window = Ui()  # Create an instance of our class
    app.exec_()  # Start the application
