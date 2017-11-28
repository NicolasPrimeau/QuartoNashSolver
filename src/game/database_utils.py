from pymongo import MongoClient, ReplaceOne


class DBInterface:

    def __init__(self, database, collection=None):
        self.database = database
        self.collection = collection
        self.db_client = MongoClient()

    def find_one(self, state):
        return self.db_client[self.database][self.collection].find_one({"state_key": state.key})

    def find_one_multistate(self, states):
        keys = [state.key for state in states]
        return self.db_client[self.database][self.collection].find_one({"state_key": {"$in": keys}})

    def insert_data(self, state, value_mapping):
        item = {"state_key": state.key, "state": state.encode(),
                "action_mapping": {action.encode(): action.value for action in value_mapping}}
        self.db_client[self.database][self.collection].replace_one({"state_key": state.key}, item, upsert=True)

    def update(self, state, action):
        key = state.key
        self.db_client[self.database][self.collection].update_one({"state_key": key}, {"$set": {
            "action_mapping.{}".format(action.encode()): action.value
        }})


class Cache:

    def __init__(self, database, collection=None):
        self.database = database
        self._collection = collection
        self._storage = dict()
        self.db_client = MongoClient()

    @property
    def collection(self):
        return self._collection

    @collection.setter
    def collection(self, value):
        self._collection = value
        self.load()

    def find_one(self, state):
        return self.find_one_multistate([state])

    def find_one_multistate(self, states):
        for state in states:
            key = state.key
            if key in self._storage:
                return self._storage[key]
        return None

    def add_data(self, state, data):
        self._storage[state.key] = data

    def insert_data(self, state, value_mapping):
        item = {"state_key": state.key, "state": state.encode(),
                "action_mapping": {action.encode(): action.value for action in value_mapping}}
        self.add_data(state, item)

    def update(self, state, action):
        self.find_one(state)["action_mapping"][action.encode()] = action.value
        key = state.key
        self.db_client[self.database][self.collection].update_one({"state_key": key}, {"$set": {
            "action_mapping.{}".format(action.encode): action.value
        }})

    def load(self):
        for item in self.db_client[self.database][self.collection].find():
            self._storage[item["state_key"]] = item

    def save(self):
        pass


class DatabaseUpdater:

    def __init__(self, data_queue, database, collection=None, batch_size=100):
        self.database = database
        self.collection = collection
        self.die = False
        self.queue = data_queue
        self._batch_size = batch_size

    def start(self):
        db_client = MongoClient()
        db = db_client[self.database]
        bulk_ops = dict()
        while not self.die:
            bulk_ops = dict()
            while len(bulk_ops) < self._batch_size:
                item = self.queue.get()
                bulk_ops[item["state_key"]] = ReplaceOne({"state_key": item["state_key"]}, item, upsert=True)
                self.queue.task_done()
            db[self.collection].bulk_write(list(bulk_ops.values()))
        db[self.collection].bulk_write(list(bulk_ops.values()))

    def kill(self):
        self.die = True
