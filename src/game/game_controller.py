import argparse
import os

from game.complex_players import ReinforcedPlayer
from game.players import HumanTerminalPlayer, RandomPlayer
from game.quatro import QuartoGame, GameError

PLAYER_TYPE_MAP = {
    "terminal": HumanTerminalPlayer,
    "random": RandomPlayer,
    "ai": ReinforcedPlayer
}


def get_player_type(player_type):
    return PLAYER_TYPE_MAP[player_type]


class RunInstance:

    DIMENSION_1 = {"white", "black"}
    DIMENSION_2 = {"hole", "solid"}
    DIMENSION_3 = {"tall", "short"}
    DIMENSION_4 = {"round", "square"}

    def __init__(self, player1_type, player2_type, cache1=None, cache2=None, verbose=False):
        self.p1_type = player1_type
        self.p2_type = player2_type
        self.verbose = verbose
        self.cache1 = cache1
        self.cache2 = cache2

    def run(self):
        dimensions = [self.DIMENSION_1, self.DIMENSION_2, self.DIMENSION_3, self.DIMENSION_4]
        game_instance = QuartoGame(dimensions=dimensions)
        controller = GameController(game=game_instance,
                                    player1=self.p1_type("Player 1", game_instance=game_instance, cache=self.cache1),
                                    player2=self.p2_type("Player 2", game_instance=game_instance, cache=self.cache2),
                                    verbose=self.verbose)
        result = controller.play()
        return result.name if result is not None else "None"


class GameController:

    def __init__(self, game, player1, player2, p1_start=True, verbose=False):
        self.game = game
        self.playing = player1 if p1_start else player2
        self.waiting = player2 if p1_start else player1
        self.verbose = verbose

    def turn(self):
        token = self.waiting.choose_token(self.game.remaining_tokens)
        x, y = self.playing.place_token(token)
        while True:
            try:
                self.game.place_token(token, x, y)
                break
            except GameError as e:
                print("That's not a proper token position, try again.\n", e)
                x, y = self.playing.place_token(token)

    @staticmethod
    def header():
        print("=" * 25)
        print("Welcome to Quarto!")
        print("=" * 25)

    def play(self):
        if self.verbose:
            self.header()
            first = True
        while not self.game.winner and not self.game.tie:
            if self.verbose:
                self.print_game_board(clear=not first)
                first = False
            self.turn()
            self.playing, self.waiting = self.waiting, self.playing
        if self.verbose:
            self.footer(won=self.game.winner)
        if self.game.winner:
            self.waiting.inform_of_outcome(1.0)
            self.playing.inform_of_outcome(-1.0)
        else:
            self.waiting.inform_of_outcome(0.0)
            self.playing.inform_of_outcome(0.0)
        return self.waiting if self.game.winner else None

    def footer(self, won=True):
        self.print_game_board()
        print()
        print("=" * 25)
        if won:
            print("Congrats on winning! " + self.waiting.name)
        else:
            print("Tie...")
        print("=" * 25)
        print()

    def print_game_board(self, clear=True):
        if clear:
            os.system('cls' if os.name == 'nt' else 'clear')
        print(str(self.game))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-p1", "--player1-type", dest="player1", help="Player 1 type",
                        choices=["terminal", "random", "ai"], required=False, default="ai")
    parser.add_argument("-p2", "--player2-type", dest="player2", help="Player 2 type",
                        choices=["terminal", "random", "ai"], required=False, default="ai")
    args = parser.parse_args()
    RunInstance(player1_type=PLAYER_TYPE_MAP[args.player1], player2_type=PLAYER_TYPE_MAP[args.player2], verbose=True)\
        .run()
