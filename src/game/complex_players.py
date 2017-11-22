import itertools
import random
from game.players import Player
from pymongo import MongoClient


class Action:

    def __init__(self, token=None, position=None, returned_token=None, value=0.0, encoded_action=None):
        if None not in (token, position, returned_token, value):
            self.token = token
            self.position = position
            self.returned_token = returned_token
            self.value = value
        elif encoded_action is not None:
            self.decode(encoded_action)
            self.value = value
        else:
            raise ValueError("Don't do that")

    def encode(self):
        return "{},{},{},{}".format(self.token, self.position[0], self.position[1], self.returned_token)

    def decode(self, encoded_action):
        token, i, j, returned_token, value = encoded_action.split(",")
        self.token = int(token)
        self.position = (int(i), int(j))
        self.returned_token = int(returned_token)


class Reasoning:

    _database = "Quarto"
    _given_token_indicator = "Given"

    def __init__(self, name, game_state, alpha=0.1, gamma=0.95):
        self._collection = "{}-Memory".format(name)
        self.db_client = MongoClient()
        self.alpha = alpha
        self.gamma = gamma
        self._action_route = list()
        self._internal_state = None

    def get_action(self, game_state, given_token_id):
        self._internal_state = list(game_state)
        self._internal_state[given_token_id] = self._given_token_indicator
        # If they're equal, we don't care
        chosen = self._get_best_action()
        old_state = list(self._internal_state)
        self._internal_state[chosen.token] = chosen.position
        self._action_route.append((old_state, chosen, list(self._internal_state)))
        return chosen

    def give_reward(self, reward):
        for i in range(len(self._action_route)):
            current_state = self._action_route[i][0]
            chosen_action = self._action_route[i][1]
            best_next = self._get_best_action(state=self._action_route[i][2])
            discount_factor = self.gamma ** (len(self._action_route) - i)
            new_value = (1 - self.alpha) * chosen_action.value
            new_value += self.alpha * (reward + discount_factor * best_next.value)
            chosen_action.value = new_value
            self._update_action_mapping(current_state, chosen_action)

    def _update_action_mapping(self, state, action):
        self.db_client[self._database][self._collection]\
            .update_one({"state": state}, {"$set": {"action_mapping.{}".format(action.encode()): action.value}})

    def _get_possible_actions(self):
        remaining = set()
        free_cells = set((i, j) for i, j in itertools.product(range(int(len(self._internal_state)**0.5)),
                                                            range(int(len(self._internal_state)**0.5))))
        for element in range(len(self._internal_state)):
            if self._internal_state[element] is not None and \
                            self._internal_state[element] != self._given_token_indicator:
                free_cells.remove(self._internal_state[element])
            elif self._internal_state[element] is not self._given_token_indicator:
                remaining.add(element)
        possible_actions = list()
        for token in remaining:
            for cell in free_cells:
                for give_back in filter(lambda x: x != token, remaining):
                    possible_actions.append(Action(token, cell, give_back))
        return possible_actions

    def _init_state_value_mapping(self, value_mapping, state=None):
        internal_state = self._internal_state
        if state is not None:
            internal_state = state
        self.db_client[self._database][self._collection].insert({
            "state": internal_state,
            "action_mapping": {action.encode(): action.value for action in value_mapping}
        })

    def _get_best_action(self, state=None):
        return max(self._get_action_values(state=state), key=lambda action: action.value)

    def _get_action_values(self, state=None):
        internal_state = self._internal_state
        if state is not None:
            internal_state = state
        state_actions = self.db_client[self._database][self._collection].find_one(internal_state)
        if state_actions is None:
            state_actions = self._get_possible_actions()
            self._init_state_value_mapping(state_actions, state=internal_state)
        else:
            state_actions = [Action(encoded_action=key, value=val) for key, val in state_actions.items()]
        return state_actions


class ReinforcedPlayer(Player):

    _database = "Quarto"

    def __init__(self, name, game_instance=None):
        super().__init__(name=name, game_instance=game_instance)
        self.reasoner = Reasoning(name, game_instance.state)
        self._action = None

    def place_token(self, token):
        self._action = self.reasoner.get_action(self.game_instance.state,
                                                self.game_instance.get_token_unique_id(token))
        return self._action.position

    def choose_token(self, tokens):
        if self._action is None:
            return random.choice(list(tokens))
        return self.game_instance.get_token_from_unique_id(self._action.returned_token)

    def inform_of_outcome(self, result):
        if result == 1:
            reward = 1.0
        elif result == -1:
            reward = -1.0
        elif result == 0:
            reward = 0.0
        else:
            raise ValueError("Don't do that")
        self.reasoner.give_reward(reward)
