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
    def __init__(self, show_id: bool = True, show_name: bool = True, show_age: bool = True, show_salary: bool = True, show_gender: bool = True):
        self.show_id = show_id
        self.show_name = show_name
        self.show_age = show_age
        self.show_salary = show_salary
        self.show_gender = show_gender

    def and_mask(self, other: "FieldMask") -> "FieldMask":
        return FieldMask(
            show_id=self.show_id and other.show_id,
            show_name=self.show_name and other.show_name,
            show_age=self.show_age and other.show_age,
            show_salary=self.show_salary and other.show_salary,
            show_gender=self.show_gender and other.show_gender
        )

    def or_mask(self, other: "FieldMask") -> "FieldMask":
        return FieldMask(
            show_id=self.show_id or other.show_id,
            show_name=self.show_name or other.show_name,
            show_age=self.show_age or other.show_age,
            show_salary=self.show_salary or other.show_salary,
            show_gender=self.show_gender or other.show_gender
        )

    def not_mask(self) -> "FieldMask":
        return FieldMask(
            show_id=not self.show_id,
            show_name=not self.show_name,
            show_age=not self.show_age,
            show_salary=not self.show_salary,
            show_gender=not self.show_gender
        )

class Database:
    def __init__(self):
        self.objects: list[Person] = []

    def add(self, obj: Person) -> None:
        self.objects.append(obj)

    def find_by_name(self, name: str) -> list[Person]:
        return [obj for obj in self.objects if obj.name == name]

    def merge_by_mask(self, mask: FieldMask) -> list[Person]:
        """Объединяет объекты, равные по маске и возвращает список новых объектов."""
        merged: list[Person] = []
        visited: set[int] = set()

        for i, obj1 in enumerate(self.objects):
            if i in visited:
                continue

            group = [obj1]
            for j, obj2 in enumerate(self.objects[i + 1:], start=i + 1):
                if self._equals_by_mask(obj1, obj2, mask):
                    group.append(obj2)
                    visited.add(j)

            merged_obj = self._merge_group(group, mask)
            merged.append(merged_obj)

        return merged

    @staticmethod
    def _equals_by_mask(p1: Person, p2: Person, mask: FieldMask) -> bool:
        """Сравнивает два объекта по маске"""
        if mask.show_id and p1.person_id != p2.person_id:
            return False
        if mask.show_name and p1.name != p2.name:
            return False
        if mask.show_age and p1.age != p2.age:
            return False
        if mask.show_salary and p1.salary != p2.salary:
            return False
        if mask.show_gender and p1.gender != p2.gender:
            return False
        return True

    @staticmethod
    def _merge_group(group: list[Person], mask: FieldMask) -> Person:
        """Создаёт новый объект на основе слитой группы"""
        base = group[0]
        avg_age = sum(p.age for p in group) / len(group)
        avg_salary = sum(p.salary for p in group) / len(group)
        return Person(
            person_id=base.person_id,
            name=base.name,
            age=int(avg_age),           # средний возраст
            salary=round(avg_salary, 2),# средняя зарплата
            gender=base.gender
        )

    def copy_fields_by_mask(self, source: Person, mask_match: FieldMask, mask_copy: FieldMask) -> None:
        """Копирует данные из source в объекты, совпадающие по mask_match. mask_copy - задает поля для копирования."""


        for obj in self.objects:
            if self._equals_by_mask(obj, source, mask_match):
                # Копируем только те поля, которые разрешены mask_copy
                if mask_copy.show_id:
                    obj.person_id = source.person_id
                if mask_copy.show_name:
                    obj.name = source.name
                if mask_copy.show_age:
                    obj.age = source.age
                if mask_copy.show_salary:
                    obj.salary = source.salary
                if mask_copy.show_gender:
                    obj.gender = source.gender


class Printer:
    @staticmethod
    def print_person(person: Person, mask: FieldMask) -> None:
        parts: list[str] = []
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

    #1 merge of masks
    mask = FieldMask(show_name=True, show_id=False, show_age=False, show_salary=False, show_gender=True)
    merged = db.merge_by_mask(mask)

    for p in merged:
        Printer.print_person(p, FieldMask())
    print()

    #2mask copy

    source = Person(99, "Alice", 35, 5000, Gender.FEMALE) #Эталон

    # Маска совпадения (тут ищем по имени)
    mask_match = FieldMask(show_name=True, show_id=False, show_age=False, show_salary=False, show_gender=False)

    # Маска для копирования (что именно копируем из эталона)
    mask_copy = FieldMask(show_age=True, show_salary=True, show_id=False, show_name=False, show_gender=False)

    # копирование
    db.copy_fields_by_mask(source, mask_match, mask_copy)

    for p in db.find_by_name("Alice"):
        Printer.print_person(p, FieldMask())
    print()

    #3 and, or, not
    mask1 = FieldMask(show_id=True, show_name=True, show_age=False, show_salary=False, show_gender=True)
    mask2 = FieldMask(show_id=False, show_name=True, show_age=True, show_salary=False, show_gender=False)

    mask_and = mask1.and_mask(mask2)
    mask_or = mask1.or_mask(mask2)
    mask_not = mask1.not_mask()

    print("AND:", mask_and.__dict__)
    print("OR:", mask_or.__dict__)
    print("NOT:", mask_not.__dict__)
