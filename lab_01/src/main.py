from enum import Enum

class Gender(Enum):
    MALE = "Male"
    FEMALE = "Female"

class Person:
    def __init__(self, person_id: int, name: str, age: int, salary: float, gender: Gender):
        self.person_id = person_id
        self.name = name
        self.age = age
        self.salary = salary
        self.gender = gender

class FieldMask:
    def __init__(self, show_id=True, show_name=True, show_age=True, show_salary=True, show_gender=True):
        self.show_id = show_id
        self.show_name = show_name
        self.show_age = show_age
        self.show_salary = show_salary
        self.show_gender = show_gender

class Database:
    def __init__(self):
        self.objects = []

    def add(self, obj: Person):
        self.objects.append(obj)

    def find_by_name(self, name: str):
        return [obj for obj in self.objects if obj.name == name]


class Printer:
    @staticmethod
    def print_person(person: Person, mask: FieldMask) -> None:
        parts = []
        if mask.show_id:     parts.append(f"ID: {person.person_id}")
        if mask.show_name:   parts.append(f"Name: {person.name}")
        if mask.show_age:    parts.append(f"Age: {person.age}")
        if mask.show_salary: parts.append(f"Salary: {person.salary}")
        if mask.show_gender: parts.append(f"Gender: {person.gender.value}")
        print(", ".join(parts))


#Mask-merge


if __name__ == "__main__":
    db = Database()
    db.add(Person(1, "Alice", 25, 3000.0, Gender.FEMALE))
    db.add(Person(2, "Bob",   30, 4000.0, Gender.MALE))
    db.add(Person(3, "Alice", 28, 3500.0, Gender.FEMALE))

    mask = FieldMask(show_id=False, show_name=True, show_age=False, show_salary=True, show_gender=False)
    for p in db.find_by_name("Alice"):
        Printer.print_person(p, mask)