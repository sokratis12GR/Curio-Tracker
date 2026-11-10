from abc import ABC, abstractmethod

from config import csv_record_header


def _record_int(value):
    text = str(value).strip()
    return int(text) if text.isdigit() else None


def max_record_number(rows):
    numbers = [_record_int(row.get(csv_record_header, "")) for row in rows]
    return max((n for n in numbers if n is not None), default=0)


def shift_records_after_delete(rows, deleted_number):
    #############################################################
    # Keeps record numbers continuous: every record numbered    #
    # above the deleted one moves down by one.                  #
    #############################################################
    deleted = _record_int(deleted_number)
    if deleted is None:
        return

    for row in rows:
        number = _record_int(row.get(csv_record_header, ""))
        if number is not None and number > deleted:
            row[csv_record_header] = str(number - 1)


class BaseDataManager(ABC):

    @abstractmethod
    def load_dict(self):
        pass

    @abstractmethod
    def save_dict(self, root, rows, fieldnames):
        pass

    @abstractmethod
    def get_next_record_number(self, force=False):
        pass

    @abstractmethod
    def modify_record(self, root, record_number, item_name, updates=None, delete=False):
        pass

    @abstractmethod
    def upgrade_structure(self):
        pass

    @abstractmethod
    def duplicate_latest(self, root):
        pass

    @abstractmethod
    def ensure_data_file(self):
        pass

    @abstractmethod
    def recalculate_record_number(self):
        pass

    def get_record_count(self):
        # Number of data rows; subclasses override with something cheaper.
        return len(self.load_dict())
