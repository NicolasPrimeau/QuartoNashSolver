
import os

from game.players import HumanTerminalPlayer, RandomPlayer
from game.quatro import QuartoGame, GameError


class RunInstance:

    PLAYER_1 = RandomPlayer
    PLAYER_2 = RandomPlayer
    DIMENSION_1 = {"white", "black"}
    DIMENSION_2 = {"hole", "solid"}
    DIMENSION_3 = {"tall", "short"}
    DIMENSION_4 = {"round", "square"}

    def __init__(self, verbose=False):
        self.verbose = verbose

    def run(self):
        dimensions = [self.DIMENSION_1, self.DIMENSION_2, self.DIMENSION_3, self.DIMENSION_4]
        game_instance = QuartoGame(dimensions=dimensions)
        controller = GameController(game=game_instance,
                                    player1=self.PLAYER_1("Player 1", game_instance=game_instance),
                                    player2=self.PLAYER_2("Player 2", game_instance=game_instance),
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
                print("That's not a proper token position, try again.\n")
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
    RunInstance().run()
