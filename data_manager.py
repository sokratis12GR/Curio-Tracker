from abc import ABC, abstractmethod

class BaseDataManager(ABC):

    @abstractmethod
    def load_dict(self):
        pass

    @abstractmethod
    def save_dict(self, root, rows, fieldnames):
        pass

    @abstractmethod
    def get_next_record_number(self):
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