from pymongo import MongoClient, ReplaceOne

import game.core_elements
from game.core_elements import State


class StateDBInterface:

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


class StateCache:

    def __init__(self, database, collection=None):
        self.database = database
        self.collection = collection
        self._storage = dict()
        self.db_client = MongoClient()

    def find_one(self, state):
        if state.key not in self._storage:
            item = self.db_client[self.database][self.collection].find_one({"state_key": state.key})
            if item is not None:
                self._storage[state.key] = item
            else:
                return None
        return self._storage[state.key]

    def find_one_multistate(self, states):
        keys = [state.key for state in states]
        for key in keys:
            if key in self._storage:
                return self._storage[key]
        item = self.db_client[self.database][self.collection].find_one({"state_key": {"$in": keys}})
        if item is not None:
            self._storage[item.key] = item
            return item
        else:
            return None

    def insert_data(self, state, value_mapping):
        item = {"state_key": state.key, "state": state.encode(),
                "action_mapping": {action.encode(): action.value for action in value_mapping}}
        self.db_client[self.database][self.collection].replace_one({"state_key": state.key}, item, upsert=True)
        self._storage[state.key] = item

    def update(self, state, action):
        self.find_one(state)["action_mapping"][action.encode()] = action.value
        self.db_client[self.database][self.collection].update_one({"state_key": state.key}, {"$set": {
            "action_mapping.{}".format(action.encode()): action.value
        }})


class StateEquivalencyCache:

    def __init__(self, database, collection=None):
        self.database = database
        self.collection = collection
        self._storage = dict()
        self.db_client = MongoClient()

    def find_one(self, state):
        if state.key not in self._storage:
            item = self.db_client[self.database][self.collection].find_one({"state_key": state.key})
            if item is not None:
                self._storage[state.key] = item
            else:
                return None, None
        equivalent_state = State(self._storage[state.key]["state"], state.dimensions)
        transform_type = self._storage[state.key]["transform_type"]
        if transform_type is not None:
            transform_type = getattr(game.core_elements, transform_type)
            transform = transform_type(encoded=self._storage[state.key]["transform_parameters"])
        else:
            transform = None
        return equivalent_state, transform

    def insert_data(self, state, transformed_state, transform):
        item = {
            "state_key": state.key,
            "state": state.encode(),
            "transformed_state_key": transformed_state.key,
            "transformed_state": transformed_state.encode(),
            "transform_parameters": None if transform is None else transform.encode(),
            "transform_type": None if transform is None else type(transform)
        }
        self.db_client[self.database][self.collection].replace_one({"state_key": state.key}, item, upsert=True)
        self._storage[state.key] = item


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
