import itertools
import random
from game.players import Player
from pymongo import MongoClient
from abc import ABC, abstractmethod
import numpy as np

from game.quatro import get_token_from_unique_id, QuartoToken, get_token_unique_id


class Action:

    def __init__(self, token=None, position=None, returned_token=None, value=0.0, encoded_action=None):
        if None not in (token, position, value):
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
        token, i, j, returned_token = encoded_action.split(",")
        self.token = int(token)
        self.position = (int(i), int(j))
        self.returned_token = int(returned_token)


class State:

    _given_token_indicator = "Given"

    def __init__(self, state, dimensions):
        self._state = list(state)
        self.dimensions = dimensions

    def get_token_ids(self):
        for i in range(len(self._state)):
            yield i

    def get_token_id_status(self, token_id):
        return self._state[token_id]

    def set_token_as_given(self, token_id):
        self._state[token_id] = self._given_token_indicator

    def set_token_position(self, token_id, position):
        self._state[token_id] = position

    def encode(self):
        return list(self._state)

    def is_token_placed(self, token_id):
        return self._state[token_id] is not None and not self.is_chosen_token(token_id)

    def is_chosen_token(self, token_id):
        return self._state[token_id] == self._given_token_indicator

    def get_chosen_token(self):
        return self._state.index(self._given_token_indicator)

    def is_token_remaining(self, token_id):
        return self._state[token_id] is None

    def iterate_transformations(self):
        dim = len(self.dimensions)
        dim_possibilities = [[i for i in range(len(self.dimensions[j]) -1)] for j in range(len(self.dimensions))]
        for permutation in itertools.product(*dim_possibilities):
            for rotation in range(0, 4):
                yield ChainTransform((PermutationTransform(permutation, self.dimensions),
                                      RotationTransform(rotation, dim=dim)))


class StateTransformError(Exception):
    pass


class StateTransform(ABC):

    @abstractmethod
    def transform_state(self, state):
        pass

    @abstractmethod
    def transform_action(self, action):
        pass


class ChainTransform(StateTransform):

    def __init__(self, transforms):
        self.transforms = transforms

    def transform_state(self, state):
        for transform in self.transforms:
            state = transform.transform_state(state)
        return state

    def transform_action(self, action):
        for transform in self.transforms:
            action = transform.transform_action(action)
        return action


class RotationTransform(StateTransform):

    def __init__(self, number_of_rotations, dim=4):
        self.dim = dim
        self.number_of_rotations = number_of_rotations

    def transform_state(self, state):
        encoded_state = state.encode()
        state_matrix = [[None for i in range(self.dim)] for j in range(self.dim)]
        for i in range(len(encoded_state)):
            row = int(i/self.dim)
            col = i % self.dim
            state_matrix[row][col] = encoded_state[i]
        return State(np.rot90(m=state_matrix, k=self.number_of_rotations).flatten().tolist(), state.dimensions)

    def transform_action(self, action):
        state_matrix = [[0 for i in range(self.dim)] for j in range(self.dim)]
        state_matrix[action.position[0]][action.position[1]] = 1
        rotated_matrix = np.rot90(state_matrix, k=-self.number_of_rotations)
        token_position = np.where(rotated_matrix == 1)
        return Action(token=action.token, position=(token_position[0][0], token_position[1][0]),
                      returned_token=action.returned_token, value=action.value)


class PermutationTransform(StateTransform):

    def __init__(self, permutation, dimensions):
        self.dimensions = dimensions
        self.permutation = tuple(permutation)

    def transform_state(self, state):
        if self.dimensions != state.dimensions:
            raise StateTransformError("Why are you using games with two dimensions???")
        encoded_state = [None for i in range(len(state.encode()))]
        for token_id in state.get_token_ids():
            new_token = self._transform_token(get_token_from_unique_id(token_id, self.dimensions))
            new_token_id = get_token_unique_id(new_token, self.dimensions)
            new_status = state.get_token_id_status(new_token_id)
        return State(encoded_state, self.dimensions)

    def _transform_token(self, token):
        ordered_dimensions = [list(d) for d in self.dimensions]
        indexed_token_dimensions = [ordered_dimensions[i].index(token.dimensions[i])
                                    for i in range(len(self.dimensions))]
        permuted_token_dimensions = [(indexed_token_dimensions[i] + self.permutation[i])
                                     for i in range(len(self.dimensions))]
        permuted_token = QuartoToken(tuple(ordered_dimensions[i][permuted_token_dimensions[i]]
                                           for i in range(len(permuted_token_dimensions))))
        return permuted_token

    def transform_action(self, action):
        token_id = get_token_unique_id(
            self._inverse_transform_token(get_token_unique_id(action.chosen, self.dimensions)),
            self.dimensions)
        returned_token_id = get_token_unique_id(
            self._inverse_transform_token(get_token_unique_id(action.returned_token, self.dimensions)),
            self.dimensions)
        return Action(token=token_id, position=action.position, returned_token=returned_token_id, value=action.value)

    def _inverse_transform_token(self, token):
        ordered_dimensions = [list(d) for d in self.dimensions]
        indexed_token_dimensions = [ordered_dimensions[i].index(token.dimensions[i])
                                    for i in range(len(self.dimensions))]
        permuted_token_dimensions = [(indexed_token_dimensions[i] - self.permutation[i])
                                     for i in range(len(self.dimensions))]
        permuted_token = QuartoToken(tuple(ordered_dimensions[i][permuted_token_dimensions[i]]
                                           for i in permuted_token_dimensions))
        return permuted_token


class Reasoning:

    _database = "Quarto"

    def __init__(self, name, dimensions, alpha=0.1, gamma=0.95, exploration=0.05):
        self._collection = "{}-Memory".format(name)
        self.dimensions = dimensions
        self.db_client = MongoClient()
        self.alpha = alpha
        self.gamma = gamma
        self.exploration_probability = exploration
        self._state_transformation = None
        self._action_route = list()
        self._internal_state = None

    def get_action(self, game_state, given_token_id):
        self._internal_state = State(game_state, self.dimensions)
        self._internal_state.set_token_as_given(given_token_id)
        # If they're equal, we don't care
        self._internal_state, self._state_transformation = self._disambiguate_state()
        if random.random() > self.exploration_probability:
            action = self._get_best_action()
        else:
            action = self._get_random_action()
        self._save_meta_data(action)
        return action if self._state_transformation is None else self._state_transformation.transform_action(action)

    def give_reward(self, reward):
        for i in range(len(self._action_route)):
            current_state = self._action_route[i][0]
            chosen_action = self._action_route[i][1]
            state_actions = self.db_client[self._database][self._collection].find_one(
                {"state": self._action_route[i][2].encode()})
            if state_actions is not None:
                action_values = state_actions["action_mapping"]
                actions = [Action(encoded_action=key, value=val) for key, val in action_values.items()]
                best_next_value = max(actions, key=lambda action: action.value).value
            else:
                best_next_value = 0

            discount_factor = self.gamma ** (len(self._action_route) - i)
            new_value = (1 - self.alpha) * chosen_action.value
            new_value += self.alpha * (reward + discount_factor * best_next_value)
            chosen_action.value = new_value
            self._update_action_mapping(current_state, chosen_action)

    def _save_meta_data(self, action):
        old_state = State(self._internal_state.encode(), self.dimensions)
        self._internal_state.set_token_position(action.token, action.position)
        self._action_route.append((old_state, action, State(self._internal_state.encode(), self.dimensions)))

    def _update_action_mapping(self, state, action):
        self.db_client[self._database][self._collection]\
            .update_one({"state": state.encode()},
                        {"$set": {"action_mapping.{}".format(action.encode()): action.value}})

    def _get_possible_actions(self):
        remaining = set()
        free_cells = set((i, j) for i, j in itertools.product(range(len(self.dimensions)),
                                                              range(len(self.dimensions))))
        for element in range(len(self._internal_state.encode())):
            if self._internal_state.is_token_placed(element):
                free_cells.remove(self._internal_state.get_token_id_status(element))
            elif self._internal_state.is_token_remaining(element):
                remaining.add(element)

        possible_actions = list()
        chosen_token = self._internal_state.get_chosen_token()
        for cell in free_cells:
            for token in remaining:
                possible_actions.append(Action(chosen_token, cell, token))
        if len(possible_actions) == 0:
            possible_actions.append(Action(chosen_token, list(free_cells)[0], None))
        return possible_actions

    def _init_state_value_mapping(self, value_mapping):
        self.db_client[self._database][self._collection].insert({
            "state": self._internal_state.encode(),
            "action_mapping": {action.encode(): action.value for action in value_mapping}
        })

    def _get_best_action(self):
        return max(self._get_action_values(), key=lambda action: action.value)

    def _disambiguate_state(self, state=None):
        state = state if state is not None else self._internal_state
        for transformation in state.iterate_transformations():
            state_transformation = transformation
            equivalent_state = transformation.transform_state(state)
            matched = self.db_client[self._database][self._collection].count({"state": equivalent_state.encode()})
            if matched == 1:
                return equivalent_state, state_transformation
        return state, None

    def _get_random_action(self):
        return random.choice(self._get_action_values())

    def _get_action_values(self):
        state_actions = self.db_client[self._database][self._collection].find_one(
            {"state": self._internal_state.encode()})

        if state_actions is None:
            actions = self._get_possible_actions()
            self._init_state_value_mapping(actions)
        else:
            action_values = state_actions["action_mapping"]
            actions = [Action(encoded_action=key, value=val) for key, val in action_values.items()]
        return actions


class ReinforcedPlayer(Player):

    _database = "Quarto"

    def __init__(self, name, game_instance=None):
        super().__init__(name=name, game_instance=game_instance)
        self.reasoner = Reasoning(name, dimensions=game_instance.dimensions)
        self._action = None

    def place_token(self, token):
        self._action = self.reasoner.get_action(self.game_instance.state,
                                                self.game_instance.get_token_unique_id(token))
        return self._action.position

    def choose_token(self, tokens):
        if self._action is None:
            return random.choice(list(tokens))
        if self._action.returned_token is None:
            return None
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
