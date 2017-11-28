import itertools
import random

from game.core_elements import State, Action
from game.database_utils import Cache
from game.players import Player


class Reasoning:

    _database = "Quarto"

    def __init__(self, name, dimensions, cache=None, alpha=0.1, gamma=0.95, exploration=0.05):
        self._collection = "{}-Memory".format(name)
        self.dimensions = dimensions
        self._cache = cache
        if self._cache.collection is None:
            self._cache.collection = self._collection
        self.alpha = alpha
        self.gamma = gamma
        self.exploration_probability = exploration
        self._state_transformation = None
        self._action_route = list()
        self._internal_state = None
        if cache is None:
            self._cache = Cache(database=self._database, collection=self._collection)
        else:
            self._cache = cache

    def get_action(self, game_state, given_token_id):
        self._internal_state = State(game_state, self.dimensions)
        self._state_transformation = None
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

            state_actions = self._cache.find_one(self._action_route[i][2])

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
        self._cache.update(state, action)

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
                possible_actions.append(Action(chosen_token, list(cell), token))
        if len(possible_actions) == 0:
            possible_actions.append(Action(chosen_token, list(free_cells)[0], None))
        return possible_actions

    def _init_state_value_mapping(self, value_mapping):
        self._cache.insert_data(self._internal_state, value_mapping)

    def _get_best_action(self):
        return max(self._get_action_values(), key=lambda action: action.value)

    def _disambiguate_state(self, state=None):
        state = state if state is not None else self._internal_state
        equivalent_states = [(transform, transform.transform_state(state))
                             for transform in state.iterate_transformations()]

        matched = self._cache.find_one_multistate(list(map(lambda x: x[1], equivalent_states)))

        if matched is None:
            return state, None
        else:
            for transform, transformed_state in equivalent_states:
                if transformed_state.encode() == matched["state"]:
                    return transformed_state, transform

    def _get_random_action(self):
        return random.choice(self._get_action_values())

    def _get_action_values(self):
        state_actions = self._cache.find_one(self._internal_state)

        if state_actions is None:
            actions = self._get_possible_actions()
            self._init_state_value_mapping(actions)
        else:
            action_values = state_actions["action_mapping"]
            actions = [Action(encoded_action=key, value=val) for key, val in action_values.items()]
        return actions


class ReinforcedPlayer(Player):

    def __init__(self, name, game_instance=None, cache=None, **kwargs):
        super().__init__(name=name, game_instance=game_instance)
        self.reasoner = Reasoning(name, dimensions=game_instance.dimensions, cache=cache)
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
