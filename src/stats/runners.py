import pprint

from pymongo import MongoClient

from game.game_controller import RunInstance
import argparse
from scipy import stats
import datetime


class StatsRunner:

    def __init__(self, num_repetitions=1000, batch=None, verbose=False):
        self.stats = dict()
        self.data = None
        self.num_repetitions = num_repetitions
        self.verbose = verbose
        if batch is None:
            batch = num_repetitions*2
        self.batch = batch

    def run(self):
        self.data = list()
        self.stats["repetitions"] = 0
        for i in range(self.num_repetitions):
            self.data.append(RunInstance(verbose=self.verbose).run())
            self.stats["repetitions"] += 1
            if len(self.data) % self.batch == 0:
                self.compute_stats()
                self.log()
                yield
        self.compute_stats()
        self.log()

    def log(self):
        client = MongoClient()
        client["Quarto"]["stats"].insert(
            {
                "time": datetime.datetime.now(),
                "stats": self.stats
            }
        )

    def compute_stats(self):
        self.compute_event_counts()
        self.compute_averages()
        self.compute_statistical_significance()

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

    def compute_statistical_significance(self):
        if "event_counts" not in self.stats:
            self.compute_event_counts()
        num_result_type = len(self.stats["event_counts"]) - \
                          (1 if any(x is None for x in self.stats["event_counts"]) else 0)
        expected = 1.0 / num_result_type
        num_results = len(self.data)
        self.stats["significance"] = dict()
        for key in filter(lambda x: x != str(None), self.stats["event_counts"]):
            success_failures = (self.stats["event_counts"][key], num_results - self.stats["event_counts"][key])
            self.stats["significance"][key] = stats.binom_test(success_failures, p=expected)

    def __str__(self):
        return pprint.pformat(self.stats)

    def __repr__(self):
        return str(self)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--repetitions", dest="repetitions", help="Number of repetitions", type=int,
                        required=False, default=100)
    parser.add_argument("-b", "--batch", dest="batch", help="Batch Size", type=int,
                        required=False, default=None)
    args = parser.parse_args()
    runner = StatsRunner(args.repetitions, batch=args.batch)
    for b in runner.run():
        print(str(runner))
    print(str(runner))
