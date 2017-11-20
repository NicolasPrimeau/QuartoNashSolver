
import itertools


class GameError(Exception):
    pass


class QuartoGame:

    def __init__(self, dimensions, advanced=False):
        self.dimensions = dimensions
        self.advanced = advanced
        self.remaining_tokens = set()
        self._finished = None
        self.reset()

    @property
    def completed(self):
        if self._finished is None:
            self._finished = self._get_finished()
        return self._finished

    @property
    def winner(self):
        return len(self.completed) != 0

    @property
    def tie(self):
        return len(self.remaining_tokens) == 0

    def reset(self):
        self._finished = None
        self._build_board()
        self._extract_tokens()
        self.remaining_tokens = set(self.tokens)

    def place_token(self, token, i, j):
        if token not in self.remaining_tokens:
            raise GameError("That token has already been placed")
        if self.board[i][j] is not None:
            raise GameError("There is already a token on that spot")
        self.board[i][j] = token
        self.remaining_tokens.remove(token)
        self._finished = None

    def __str__(self):
        lines = ["| {} |".format(" | ".join(
            [str(y) if y is not None else " " * len(self.dimensions) for y in x])) for x in self.board]
        header = "+{}+".format("-" * (len(lines[0])-2))
        return "\n".join([header, *lines, header])

    def __repr__(self):
        return str(self)

    def _build_board(self):
        self.board = [[None for i in range(len(self.dimensions))] for i in range(len(self.dimensions))]

    def _extract_tokens(self):
        self.tokens = [QuartoToken(x) for x in itertools.product(*self.dimensions)]

    def _get_finished(self):
        completed = list()
        for structure in self._get_structures():
            # get the first not None
            non_nones = list(filter(None, structure))
            if len(non_nones) > 0:
                similarities = non_nones[0].get_similarities(non_nones)
                if len(non_nones) == len(structure) and any(x is not None for x in similarities):
                    completed.append(structure)
        return completed

    def _get_structures(self):
        if self.advanced:
            return [*self._get_rows(), *self._get_columns(), *self._get_diagonals(), self._get_corners(),
                    *self._get_blocks()]
        else:
            return [*self._get_rows(), *self._get_columns(), *self._get_diagonals()]

    def _get_corners(self):
        return [self.board[i][j] for i, j in itertools.product(*[[0, -1], [0, -1]])]

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

    def _get_blocks(self):
        raise NotImplementedError("I don't know the rules for this")


class QuartoToken:

    def __init__(self, set_dimensions):
        self.dimensions = list(set_dimensions)

    def get_similarities(self, others):
        if not isinstance(others, set) and not isinstance(others, list) and not isinstance(others, tuple):
            others = [others]

        sim_set = self.unique_dimensions
        for other in others:
            sim_set = sim_set.intersection(other.unique_dimensions)
        temp_vals = {idx: val for idx, val in sim_set}
        return [None if i not in temp_vals else temp_vals[i] for i in range(len(self.dimensions))]

    @property
    def unique_dimensions(self):
        return set((i, self.dimensions[i]) for i in range(len(self.dimensions)))

    def __str__(self):
        return "".join([x[0] for x in self.dimensions])

    def __repr__(self):
        return str(self)

    def _get_similarity(self, other):
        print(set(self.dimensions).intersection(set(other.dimensions)))
        return set(self.dimensions).intersection(set(other.dimensions))

    def __hash__(self):
        return "".join(x for x in self.dimensions).__hash__()

    def __eq__(self, other):
        return self.unique_dimensions() == other.unique_dimensions
