
import itertools

DIMENSION_1 = {"white", "black"}
DIMENSION_2 = {"hole", "solid"}
DIMENSION_3 = {"tall", "short"}
DIMENSION_4 = {"round", "square"}


class QuatroGame:

    def __init__(self, dimensions):
        self.dimensions = dimensions
        self.remaining_tokens = set()
        self._finished = None
        self.reset()

    @property
    def completed(self):
        if self._finished is None:
            self._finished = self._get_finished()
        return self._finished

    @property
    def done(self):
        return len(self.completed) != 0

    def reset(self):
        self._finished = None
        self._build_board()
        self._extract_tokens()
        self.remaining_tokens = set(self.tokens)

    def place_token(self, token, i, j):
        if token not in self.remaining_tokens:
            raise ValueError("That token has already been placed")
        if self.board[i][j] is not None:
            raise ValueError("There is already a token on that spot")
        self.board[i][j] = token

    def _build_board(self):
        self.board = [[None for i in range(len(self.dimensions))] for i in range(len(self.dimensions))]

    def _extract_tokens(self):
        self.tokens = [QuatroToken(x) for x in itertools.product(*self.dimensions)]

    def _get_finished(self):
        completed = list()
        # Check rows
        completed.extend(filter(lambda x: self._is_finished(x), self._get_rows()))
        # Check Columns
        completed.extend(filter(lambda x: self._is_finished(x), self._get_columns()))
        # Check Diagonals
        completed.extend(filter(lambda x: self._is_finished(x), self._get_diagonals()))
        # Check corners
        completed.extend(filter(lambda x: self._is_finished(x), [self._get_corners()]))
        return completed

    @staticmethod
    def _is_finished(tokens):
        return None not in tokens and tokens[0].get_similarities(tokens) >= 1

    def _get_corners(self):
        return [self.board[i][j] for i, j in itertools.product(*[0, -1])]

    def _get_diagonals(self):
        diagonal1 = list()
        diagonal2 = list()
        for i in range(len(self.dimensions)):
            diagonal1.append(self.board[i][i])
            diagonal2.append(self.board[i][3-i])
        return [diagonal1, diagonal2]

    def _get_rows(self):
        return [self._get_row(i) for i in range(len(self.dimensions))]

    def _get_row(self, i):
        return self.board[i]

    def _get_columns(self):
        return [self._get_column(i) for i in range(len(self.dimensions))]

    def _get_column(self, i):
        return [self.board[j][i] for j in range(len(self.dimensions))]


class QuatroToken:

    def __init__(self, set_dimensions):
        self.dimensions = set(set_dimensions)

    def get_similarities(self, other_token):
        if isinstance(other_token, set) or isinstance(other_token, list) or isinstance(other_token, tuple):
            sim_set = set()
            for other in other_token:
                sim_set = sim_set.intersection(self._get_similarity(other))
            return sim_set

        else:
            return self._get_similarity(other_token)

    def _get_similarity(self, other):
        return self.dimensions.intersection(other.dimensions)

    def __eq__(self, other):
        return self.dimensions == other.dimensions
