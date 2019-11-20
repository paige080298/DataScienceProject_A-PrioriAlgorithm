import argparse
from itertools import combinations
import collections
import csv

class TransactionManager(object):

    def __init__(self, transactions):
        self.__num_transaction = 0
        self.__items = []
        self.__transaction_index_map = {}

        for transaction in transactions:
            self.add_transaction(transaction)

    def add_transaction(self, transaction):
        for item in transaction:
            if item not in self.__transaction_index_map:
                self.__items.append(item)
                self.__transaction_index_map[item] = set()
            self.__transaction_index_map[item].add(self.__num_transaction)
        self.__num_transaction += 1

    def calc_support(self, items):
        if not items:
            return 1.0
        if not self.num_transaction:
            return 0.0
        sum_indexes = None
        for item in items:
            indexes = self.__transaction_index_map.get(item)
            if indexes is None:
                # No support for any set that contains a not existing item.
                return 0.0

            if sum_indexes is None:
                # Assign the indexes on the first time.
                sum_indexes = indexes
            else:
                # Calculate the intersection on not the first time.
                sum_indexes = sum_indexes.intersection(indexes)

        # Calculate and return the support.
        return float(len(sum_indexes)) / self.__num_transaction

    def initial_candidates(self):
        """
        Returns the initial candidates.
        """
        return [frozenset([item]) for item in self.items]

    @property
    def num_transaction(self):
        """
        Returns the number of transactions.
        """
        return self.__num_transaction

    @property
    def items(self):
        """
        Returns the item list that the transaction is consisted of.
        """
        return sorted(self.__items)

    @staticmethod
    def create(transactions):
        """
        Create the TransactionManager with a transaction instance.
        If the given instance is a TransactionManager, this returns itself.
        """
        if isinstance(transactions, TransactionManager):
            return transactions
        return TransactionManager(transactions)


# Ignore name errors because these names are namedtuples.
SupportRecord = collections.namedtuple( # pylint: disable=C0103
    'SupportRecord', ('items', 'support'))
RelationRecord = collections.namedtuple( # pylint: disable=C0103
    'RelationRecord', SupportRecord._fields + ('ordered_statistics',))
OrderedStatistic = collections.namedtuple( # pylint: disable=C0103
    'OrderedStatistic', ('items_base', 'items_add', 'confidence', 'lift',))


################################################################################
# Inner functions.
################################################################################
def create_next_candidates(prev_candidates, length):
    item_set = set()
    for candidate in prev_candidates:
        for item in candidate:
            item_set.add(item)
    items = sorted(item_set)

    # Create the temporary candidates. These will be filtered below.
    tmp_next_candidates = (frozenset(x) for x in combinations(items, length))

    # Return all the candidates if the length of the next candidates is 2
    # because their subsets are the same as items.
    if length < 3:
        return list(tmp_next_candidates)

    # Filter candidates that all of their subsets are
    # in the previous candidates.
    next_candidates = [
        candidate for candidate in tmp_next_candidates
        if all(
            True if frozenset(x) in prev_candidates else False
            for x in combinations(candidate, length - 1))
    ]
    return next_candidates


def gen_support_records(transaction_manager, min_support, **kwargs):
    """
    Returns a generator of support records with given transactions.

    Arguments:
        transaction_manager -- Transactions as a TransactionManager instance.
        min_support -- A minimum support (float).

    Keyword arguments:
        max_length -- The maximum length of relations (integer).
    """
    # Parse arguments.
    max_length = kwargs.get('max_length')

    # For testing.
    _create_next_candidates = kwargs.get(
        '_create_next_candidates', create_next_candidates)

    # Process.
    candidates = transaction_manager.initial_candidates()
    length = 1
    while candidates:
        relations = set()
        for relation_candidate in candidates:
            support = transaction_manager.calc_support(relation_candidate)
            if support < min_support:
                continue
            candidate_set = frozenset(relation_candidate)
            relations.add(candidate_set)
            yield SupportRecord(candidate_set, support)
        length += 1
        if max_length and length > max_length:
            break
        candidates = _create_next_candidates(relations, length)


def gen_ordered_statistics(transaction_manager, record):
    """
    Returns a generator of ordered statistics as OrderedStatistic instances.

    Arguments:
        transaction_manager -- Transactions as a TransactionManager instance.
        record -- A support record as a SupportRecord instance.
    """
    items = record.items
    for combination_set in combinations(sorted(items), len(items) - 1):
        items_base = frozenset(combination_set)
        items_add = frozenset(items.difference(items_base))
        confidence = (
            record.support / transaction_manager.calc_support(items_base))
        lift = confidence / transaction_manager.calc_support(items_add)
        yield OrderedStatistic(
            frozenset(items_base), frozenset(items_add), confidence, lift)


def filter_ordered_statistics(ordered_statistics, **kwargs):
    """
    Filter OrderedStatistic objects.

    Arguments:
        ordered_statistics -- A OrderedStatistic iterable object.

    Keyword arguments:
        min_confidence -- The minimum confidence of relations (float).
        min_lift -- The minimum lift of relations (float).
    """
    min_confidence = kwargs.get('min_confidence', 0.0)
    min_lift = kwargs.get('min_lift', 0.0)

    for ordered_statistic in ordered_statistics:
        if ordered_statistic.confidence < min_confidence:
            continue
        if ordered_statistic.lift < min_lift:
            continue
        yield ordered_statistic


################################################################################
# API function.
################################################################################
def apriori(transactions, **kwargs):
    min_support = kwargs.get('min_support', 0.1)
    min_confidence = kwargs.get('min_confidence', 0.0)
    min_lift = kwargs.get('min_lift', 0.0)
    max_length = kwargs.get('max_length', None)

    # Check arguments.
    if min_support <= 0:
        raise ValueError('minimum support must be > 0')

    # For testing.
    _gen_support_records = kwargs.get(
        '_gen_support_records', gen_support_records)
    _gen_ordered_statistics = kwargs.get(
        '_gen_ordered_statistics', gen_ordered_statistics)
    _filter_ordered_statistics = kwargs.get(
        '_filter_ordered_statistics', filter_ordered_statistics)

    # Calculate supports.
    transaction_manager = TransactionManager.create(transactions)
    support_records = _gen_support_records(
        transaction_manager, min_support, max_length=max_length)

    # Calculate ordered stats.
    for support_record in support_records:
        ordered_statistics = list(
            _filter_ordered_statistics(
                _gen_ordered_statistics(transaction_manager, support_record),
                min_confidence=min_confidence,
                min_lift=min_lift,
            )
        )

        if not ordered_statistics:
            continue
        yield RelationRecord(
            support_record.items, support_record.support, ordered_statistics)


def load_transactions(input_file, **kwargs):
    delimiter = kwargs.get('delimiter', '\t')
    for transaction in csv.reader(input_file, delimiter=delimiter):
        yield transaction if transaction else ['']


parser = argparse.ArgumentParser()
parser.add_argument("input_filename", help="name for input file")
parser.add_argument("output_filename", help="name for output file")
parser.add_argument('min_support',  help="minimum support value", type=float)
parser.add_argument('min_confidence',  help="minimum confidence value", type=float)
args = parser.parse_args()


f = open(args.input_filename, 'rt')
reader = csv.reader(f)
csv_list = []
for l in reader:
    if str(l).isdigit() == 0:
        csv_list.append(l[1:])
association_rules = apriori(csv_list, min_support = args.min_support, min_confidence = args.min_confidence)
test = TransactionManager.create(csv_list)
support_records1 = gen_support_records(test, args.min_support)


f = open(args.output_filename,'w')
for item in support_records1:

    pair = item[0]
    items = [x for x in pair]
    f.write("S, ")
    f.write('%.4f'%item[1])
    f.write(",")

    for i in items:
        f.write(i)

        if (items.index(i)) + 1 != len(items):
            nextelem = items[items.index(i) + 1]
            if nextelem != " ":
                f.write(",")

    f.write("\n")


for item in association_rules:
    print(item)
    for i in item[2]:
        a = 0
        if len(i[0]) == 0:
            a = 1
            do_nothing = 1
        else:
            f.write("R, ")
            f.write('%.4f' % item[1])
            f.write(",")
            f.write('%.4f' % i[2])
            f.write(",")

            for j in i[0]:
                f.write(j)
                f.write(",")

            f.write(" '=>' ")
            f.write(",")

            for j in i[1]:
                f.write(j)
                f.write(",")

            f.write("\n")


f.close()





