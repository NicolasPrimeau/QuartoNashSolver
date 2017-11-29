import itertools
import random

from game.core_elements import State, Action
from game.database_utils import StateDBInterface, StateCache, StateEquivalencyCache
from game.players import Player

caches = dict()


class Reasoning:

    _database = "Quarto"

    def __init__(self, name, dimensions, alpha=0.1, gamma=0.95, exploration=0.05):
        self._collection = "{}-Memory".format(name)
        self._transforms_collection = "{}-EquivalentState".format(name)
        if name not in caches:
            caches[name] = dict()
            caches[name][self._collection] = StateCache(database=self._database, collection=self._collection)
            caches[name][self._transforms_collection] = StateEquivalencyCache(database=self._database,
                                                                              collection=self._transforms_collection)
        self._database_interface = caches[name][self._collection]
        self._equivalency_cache = caches[name][self._transforms_collection]
        self.dimensions = dimensions
        self.alpha = alpha
        self.gamma = gamma
        self.exploration_probability = exploration
        self._state_transformation = None
        self._action_route = list()
        self._internal_state = None

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

            state_actions = self._database_interface.find_one(self._action_route[i][2])

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
        self._database_interface.update(state, action)

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
        self._database_interface.insert_data(self._internal_state, value_mapping)

    def _get_best_action(self):
        return max(self._get_action_values(), key=lambda action: action.value)

    def _disambiguate_state(self, state=None):
        state = state if state is not None else self._internal_state
        equivalent_state, transform = self._equivalency_cache.find_one(state)
        if equivalent_state is None:
            equivalent_states = [(transform, transform.transform_state(state))
                                 for transform in state.iterate_transformations()]

            matched = self._database_interface.find_one_multistate(list(map(lambda x: x[1], equivalent_states)))

            if matched is None:
                self._equivalency_cache.insert_data(state, state, None)
                return state, None
            else:
                for transform, transformed_state in equivalent_states:
                    if transformed_state.key == matched["state_key"]:
                        self._equivalency_cache.insert_data(state, transformed_state, transform)
                        return transformed_state, transform
        else:
            return equivalent_state, transform

    def _get_random_action(self):
        return random.choice(self._get_action_values())

    def _get_action_values(self):
        state_actions = self._database_interface.find_one(self._internal_state)

        if state_actions is None:
            actions = self._get_possible_actions()
            self._init_state_value_mapping(actions)
        else:
            action_values = state_actions["action_mapping"]
            actions = [Action(encoded_action=key, value=val) for key, val in action_values.items()]
        return actions


class ReinforcedPlayer(Player):

    def __init__(self, name, game_instance=None, **kwargs):
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
