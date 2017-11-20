import pprint

from game.game_controller import RunInstance
import argparse


class StatsRunner:

    def __init__(self, num_repetitions=1000, verbose=False):
        self.stats = dict()
        self.data = None
        self.stats["repetitions"] = num_repetitions
        self.verbose=verbose

    def run(self):
        self.data = [RunInstance(verbose=self.verbose).run() for i in range(self.stats["repetitions"])]
        self.compute_averages()

    def compute_event_counts(self):
        self.stats["event_counts"] = dict()
        for x in self.data:
            if x not in self.stats["event_counts"]:
                self.stats["event_counts"][x] = 0
            self.stats["event_counts"][x] += 1

    def compute_averages(self):
        if "event_counts" not in self.stats:
            self.compute_event_counts()
        self.stats["averages"] = dict()
        for key, val in self.stats["event_counts"].items():
            self.stats["averages"][key] = val/len(self.data)

    def __str__(self):
        return pprint.pformat(self.stats)

    def __repr__(self):
        return str(self)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--repetitions", dest="repetitions", help="Number of repetitions", type=int,
                        required=False, default=100)
    args = parser.parse_args()
    runner = StatsRunner(args.repetitions)
    runner.run()
    print(str(runner))
