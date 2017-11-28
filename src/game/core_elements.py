import itertools
from abc import ABC, abstractmethod

from game.quatro import get_token_from_unique_id, get_token_unique_id, QuartoToken
import numpy as np


class Action:

    def __init__(self, token=None, position=None, returned_token=None, value=0.0, encoded_action=None):
        if None not in (token, position, value):
            self.token = token
            self.position = list(position)
            self.returned_token = returned_token
            self._value = value
        elif encoded_action is not None:
            self.decode(encoded_action)
            self._value = value
        else:
            raise ValueError("Don't do that")

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, val):
        self._value = sorted([-1, val, 1])[1]

    def encode(self):
        return "{},{},{},{}".format(self.token, self.position[0], self.position[1], self.returned_token)

    def decode(self, encoded_action):
        token, i, j, returned_token = encoded_action.split(",")
        self.token = int(token)
        self.position = [int(i), int(j)]
        try:
            self.returned_token = int(returned_token)
        except ValueError:
            self.returned_token = None


class State:

    _given_token_indicator = "Given"

    def __init__(self, state, dimensions):
        self._state = list(state)
        self.dimensions = dimensions

    @property
    def key(self):
        return ",".join(map(str, self._state))

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
            state_matrix[row][col] = i
        rotated_matrix = np.rot90(m=state_matrix, k=self.number_of_rotations)
        new_state = [None for i in range(len(encoded_state))]
        for i in range(len(new_state)):
            token_position = np.where(rotated_matrix == i)
            if token_position is len(token_position[0]) == 1:
                new_state[i] = (token_position[0][0], token_position[1][0])
        return State(new_state, state.dimensions)

    def transform_action(self, action):
        state_matrix = [[0 for i in range(self.dim)] for j in range(self.dim)]
        state_matrix[action.position[0]][action.position[1]] = 1
        rotated_matrix = np.rot90(state_matrix, k=-self.number_of_rotations)
        token_position = np.where(rotated_matrix == 1)
        return Action(token=action.token, position=[token_position[0][0], token_position[1][0]],
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
            encoded_state[new_token_id] = new_status
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
            self._inverse_transform_token(get_token_from_unique_id(action.token, self.dimensions)), self.dimensions)
        returned_token_id = get_token_unique_id(self._inverse_transform_token(
                get_token_from_unique_id(action.returned_token, self.dimensions)),self.dimensions)
        return Action(token=token_id, position=action.position, returned_token=returned_token_id, value=action.value)

    def _inverse_transform_token(self, token):
        ordered_dimensions = [list(d) for d in self.dimensions]
        indexed_token_dimensions = [ordered_dimensions[i].index(token.dimensions[i])
                                    for i in range(len(self.dimensions))]
        permuted_token_dimensions = [(indexed_token_dimensions[i] - self.permutation[i])
                                     for i in range(len(self.dimensions))]
        permuted_token = QuartoToken(tuple(ordered_dimensions[i][permuted_token_dimensions[i]]
                                           for i in range(len(permuted_token_dimensions))))
        return permuted_token

