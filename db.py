from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, inspect
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime

DEBUG_DB = True

Base = declarative_base()


class Cars(Base):
    __tablename__ = 'Cars'

    id = Column(Integer, primary_key=True, autoincrement=True)
    plate = Column(String(9), nullable=False)
    direction = Column(String(25), nullable=False)
    time = Column(DateTime, nullable=False)
    employee_id = Column(Integer, ForeignKey('Employees.employee_id'))

    employee = relationship("Employees", back_populates="cars")


class Employees(Base):
    __tablename__ = 'Employees'

    employee_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(25), nullable=False)
    department = Column(String(50), nullable=False)
    car_plate = Column(String(9), nullable=False)

    cars = relationship("Cars", back_populates="employee")


class Database:
    def __init__(self, db_url="postgresql+psycopg2://postgres:HF352klpbn@localhost:5432/access_control"):
        self.db_url = db_url
        self.engine = create_engine(self.db_url)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()
        self.create_tables()

    @staticmethod
    def log_DB(message):
        if DEBUG_DB:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open('log_DB.txt', 'a') as file:
                file.write(current_time + ' ' + message + '\n')

    def create_tables(self):
        """Создание таблиц Cars и Employees, если они ещё не существуют."""
        inspector = inspect(self.engine)
        existing_tables = inspector.get_table_names()

        if "Employees" not in existing_tables:
            Base.metadata.tables['Employees'].create(self.engine)
            self.log_DB("Table 'Employees' was created")
        else:
            self.log_DB("Table 'Employees' already exists")

        if "Cars" not in existing_tables:
            Base.metadata.tables['Cars'].create(self.engine)
            self.log_DB("Table 'Cars' was created")
        else:
            self.log_DB("Table 'Cars' already exists")

    def find_employee(self, plate):
        """Поиск сотрудника по автомобильному номеру."""
        employee = self.session.query(Employees).filter_by(car_plate=plate).first()
        return employee.employee_id if employee else None

    def add_car(self, plate, direction):
        """Добавление новой записи в таблицу Cars."""
        employee_id = self.find_employee(plate)
        new_car = Cars(
            plate=plate,
            direction=direction,
            time=datetime.now(),
            employee_id=employee_id
        )
        self.session.add(new_car)
        self.session.commit()
        self.log_DB(f'New car plate <{plate}> ({"known" if employee_id else "unknown"}) was added')

    def add_employee(self, name, department, car_plate):
        """Добавление нового сотрудника в таблицу Employees."""
        new_employee = Employees(
            name=name,
            department=department,
            car_plate=car_plate
        )
        self.session.add(new_employee)
        self.session.commit()
        self.log_DB(f'New employee <{name}> was added')

    def get_all_cars(self):
        """Получение всех данных из таблицы Cars."""
        cars = self.session.query(
            Cars.plate, Employees.name, Employees.department, Cars.direction, Cars.time
        ).join(Employees, Cars.employee_id == Employees.employee_id, isouter=True).all()
        return cars

    def close(self):
        """Закрытие сессии с базой данных."""
        self.session.close()
        self.log_DB("Session was closed")
