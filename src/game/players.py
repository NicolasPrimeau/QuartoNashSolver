from abc import ABC, abstractmethod
import random


class Player(ABC):

    def __init__(self, name, game_instance):
        self.name = name
        self.game_instance = game_instance

    @abstractmethod
    def choose_token(self, tokens):
        pass

    @abstractmethod
    def place_token(self, token):
        pass


class HumanTerminalPlayer(Player):

    def __init__(self, name, game_instance=None):
        super().__init__(name=name, game_instance=game_instance)

    def print_name(self):
        print("-" * 15)
        print(self.name)
        print("-" * 15)

    def choose_token(self, tokens):
        self.print_name()
        tokens = list(tokens)
        self._print_tokens(tokens, numbered=True)
        token_id = input("Which token do you want to give? Token Id: ")
        return tokens[int(token_id)]

    def place_token(self, token):
        self.print_name()
        self._print_tokens(list(self.game_instance.remaining_tokens))
        print("Your tokens: {}".format(str(token)))
        location = input("Where do you want to place it? x, y: ")
        return [int(token) for token in location.strip().split(",")]

    @staticmethod
    def _print_tokens(tokens, numbered=False):
        print("Remaining tokens: ")
        line = list()
        for i in range(len(tokens)):
            if numbered:
                line.append("{}-{}".format(i, tokens[i]))
            else:
                line.append("{}".format(tokens[i]))
            if (i+1) % 5 == 0:
                print(", ".join(line))
                line = list()
        print(", ".join(line))
        print()


class RandomPlayer(Player):

    def __init__(self, name, game_instance=None):
        super().__init__(name=name, game_instance=game_instance)

    def choose_token(self, tokens):
        return random.choice(list(tokens))

    def place_token(self, token):
        possibilities = list()
        for i in range(len(self.game_instance.dimensions)):
            for j in range(len(self.game_instance.dimensions)):
                if self.game_instance.board[i][j] is None:
                    possibilities.append((i, j))
        return random.choice(possibilities)
