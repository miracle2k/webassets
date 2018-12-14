from threading import Lock


class LockManager(object):
    """Implementation of a manager that returns a lock based on a given key
    ``get_lock`` uses a lock to prevent multiple threads from entering it
    at the same time
    """
    def __init__(self):
        self.__locks = dict()
        self.__check_lock = Lock()

    def get_lock(self, key):
        """Returns the lock corresponding to the given key
        """
        with self.__check_lock:
            if key in self.__locks:
                return self.__locks[key]
            else:
                lock = Lock()
                self.__locks[key] = lock
                return lock
