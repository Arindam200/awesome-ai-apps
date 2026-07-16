"""Preset coding challenges: a spec the models see, and a hidden test script
that never gets shown to the contestants. Each test script expects a single
top-level `solution` object (function or class) implementing the spec, and
prints ``ALL_TESTS_PASSED`` iff every assertion holds.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class HiddenTest:
    name: str
    code: str
    weight: int = 1


@dataclass(frozen=True)
class Challenge:
    id: str
    title: str
    difficulty: str
    prompt: str
    test_code: str = ""
    test_cases: tuple[HiddenTest, ...] = ()

    @property
    def hidden_tests(self) -> tuple[HiddenTest, ...]:
        if self.test_cases:
            return self.test_cases
        return (HiddenTest(name="Complete hidden suite", code=self.test_code),)


_TWO_SUM = Challenge(
    id="two_sum",
    title="Two Sum (O(n))",
    difficulty="Easy",
    prompt=(
        "Write a Python function with this exact signature:\n\n"
        "    def two_sum(nums: list[int], target: int) -> list[int]\n\n"
        "It returns the indices of the two numbers in `nums` that add up to "
        "`target`. Assume exactly one valid answer exists and you may not "
        "use the same element twice. Must run in O(n) time, not O(n^2)."
    ),
    test_code=(
        "assert sorted(solution([2, 7, 11, 15], 9)) == [0, 1]\n"
        "assert sorted(solution([3, 2, 4], 6)) == [1, 2]\n"
        "assert sorted(solution([3, 3], 6)) == [0, 1]\n"
        "assert sorted(solution([-1, -2, -3, -4, -5], -8)) == [2, 4]\n"
        "import time\n"
        "big = list(range(50000))\n"
        "start = time.perf_counter()\n"
        "i, j = solution(big, 98)\n"
        "assert i != j and big[i] + big[j] == 98\n"
        "assert time.perf_counter() - start < 2.0, 'too slow for O(n) on 50k elements'\n"
    ),
)

_VALID_PARENS = Challenge(
    id="valid_parentheses",
    title="Valid Parentheses",
    difficulty="Easy",
    prompt=(
        "Write a Python function with this exact signature:\n\n"
        "    def is_valid(s: str) -> bool\n\n"
        "`s` contains only the characters '(', ')', '{', '}', '[' and ']'. "
        "Return True iff every bracket is closed by the same type in the "
        "correct order."
    ),
    test_code=(
        "assert solution('()') is True\n"
        "assert solution('()[]{}') is True\n"
        "assert solution('(]') is False\n"
        "assert solution('([)]') is False\n"
        "assert solution('{[]}') is True\n"
        "assert solution('') is True\n"
        "assert solution('(') is False\n"
    ),
)

_LRU_CACHE = Challenge(
    id="lru_cache",
    title="LRU Cache",
    difficulty="Medium",
    prompt=(
        "Implement a class `LRUCache` with this exact interface:\n\n"
        "    class LRUCache:\n"
        "        def __init__(self, capacity: int): ...\n"
        "        def get(self, key: int) -> int: ...  # -1 if missing\n"
        "        def put(self, key: int, value: int) -> None: ...\n\n"
        "Both `get` and `put` must run in O(1) average time. When capacity "
        "is exceeded, evict the least recently used key. A `get` or a "
        "successful `put` on an existing key both count as a use."
    ),
    test_code=(
        "c = solution(2)\n"
        "c.put(1, 1)\n"
        "c.put(2, 2)\n"
        "assert c.get(1) == 1\n"
        "c.put(3, 3)  # evicts key 2\n"
        "assert c.get(2) == -1\n"
        "c.put(4, 4)  # evicts key 1\n"
        "assert c.get(1) == -1\n"
        "assert c.get(3) == 3\n"
        "assert c.get(4) == 4\n"
    ),
)

_MERGE_INTERVALS = Challenge(
    id="merge_intervals",
    title="Merge Intervals",
    difficulty="Medium",
    prompt=(
        "Write a Python function with this exact signature:\n\n"
        "    def merge(intervals: list[list[int]]) -> list[list[int]]\n\n"
        "Merge all overlapping intervals and return the merged list, sorted "
        "by start."
    ),
    test_code=(
        "assert solution([[1, 3], [2, 6], [8, 10], [15, 18]]) == "
        "[[1, 6], [8, 10], [15, 18]]\n"
        "assert solution([[1, 4], [4, 5]]) == [[1, 5]]\n"
        "assert solution([[1, 4], [0, 4]]) == [[0, 4]]\n"
        "assert solution([]) == []\n"
        "assert solution([[1, 4]]) == [[1, 4]]\n"
    ),
)

_EVENT_RECONCILER = Challenge(
    id="event_reconciler",
    title="Production Event Reconciler",
    difficulty="Expert",
    prompt=(
        "Implement a deterministic event reconciler with this exact signature:\n\n"
        "    def reconcile_events(events: list[dict]) -> dict[str, dict]\n\n"
        "Each event contains `id` (globally unique identifier), `account`, `seq` "
        "(a positive per-account sequence number), and `kind`. Kinds are `credit`, "
        "`debit`, `freeze`, and `unfreeze`; credit/debit events also contain a "
        "positive integer `amount`. Inputs may be out of order.\n\n"
        "Rules:\n"
        "1. Deduplicate globally by event `id` before processing; the first input "
        "occurrence wins.\n"
        "2. Process each account independently in ascending `seq` order, beginning "
        "at sequence 1. At the first sequence gap, that event and all later events "
        "for the account are pending and must not change state.\n"
        "3. Credits always apply. Debits apply only when the account is not frozen "
        "and has sufficient funds. A rejected debit still consumes its sequence.\n"
        "4. Freeze/unfreeze events always apply and consume their sequence.\n"
        "5. Do not mutate the input. Return every encountered account mapped to: "
        "`balance`, `frozen`, `next_seq`, `applied_event_ids`, "
        "`rejected_event_ids`, and `pending_event_ids`. Event ID lists must be in "
        "sequence order. Empty input returns `{}`."
    ),
    test_cases=(
        HiddenTest(
            "basic ledger operations",
            "events=[{'id':'a1','account':'a','seq':1,'kind':'credit','amount':100},"
            "{'id':'a2','account':'a','seq':2,'kind':'debit','amount':35}]\n"
            "r=solution(events)['a']\n"
            "assert r=={'balance':65,'frozen':False,'next_seq':3,"
            "'applied_event_ids':['a1','a2'],'rejected_event_ids':[],"
            "'pending_event_ids':[]}",
            weight=2,
        ),
        HiddenTest(
            "out-of-order delivery",
            "events=[{'id':'x3','account':'x','seq':3,'kind':'debit','amount':4},"
            "{'id':'x1','account':'x','seq':1,'kind':'credit','amount':10},"
            "{'id':'x2','account':'x','seq':2,'kind':'credit','amount':5}]\n"
            "r=solution(events)['x']\n"
            "assert r['balance']==11 and r['next_seq']==4\n"
            "assert r['applied_event_ids']==['x1','x2','x3']",
            weight=2,
        ),
        HiddenTest(
            "global first-occurrence deduplication",
            "events=[{'id':'dup','account':'a','seq':1,'kind':'credit','amount':7},"
            "{'id':'dup','account':'a','seq':1,'kind':'credit','amount':999}]\n"
            "r=solution(events)['a']\n"
            "assert r['balance']==7 and r['applied_event_ids']==['dup']",
            weight=2,
        ),
        HiddenTest(
            "sequence gaps create pending work",
            "events=[{'id':'g1','account':'g','seq':1,'kind':'credit','amount':20},"
            "{'id':'g4','account':'g','seq':4,'kind':'credit','amount':40},"
            "{'id':'g3','account':'g','seq':3,'kind':'debit','amount':5}]\n"
            "r=solution(events)['g']\n"
            "assert r['balance']==20 and r['next_seq']==2\n"
            "assert r['pending_event_ids']==['g3','g4']",
            weight=3,
        ),
        HiddenTest(
            "freeze rejection and recovery",
            "events=[{'id':'f1','account':'f','seq':1,'kind':'credit','amount':50},"
            "{'id':'f2','account':'f','seq':2,'kind':'freeze'},"
            "{'id':'f3','account':'f','seq':3,'kind':'debit','amount':10},"
            "{'id':'f4','account':'f','seq':4,'kind':'unfreeze'},"
            "{'id':'f5','account':'f','seq':5,'kind':'debit','amount':10}]\n"
            "r=solution(events)['f']\n"
            "assert r['balance']==40 and r['frozen'] is False and r['next_seq']==6\n"
            "assert r['applied_event_ids']==['f1','f2','f4','f5']\n"
            "assert r['rejected_event_ids']==['f3']",
            weight=3,
        ),
        HiddenTest(
            "insufficient funds consume sequence",
            "events=[{'id':'i1','account':'i','seq':1,'kind':'debit','amount':1},"
            "{'id':'i2','account':'i','seq':2,'kind':'credit','amount':8}]\n"
            "r=solution(events)['i']\n"
            "assert r['balance']==8 and r['next_seq']==3\n"
            "assert r['rejected_event_ids']==['i1'] and r['applied_event_ids']==['i2']",
            weight=2,
        ),
        HiddenTest(
            "account isolation and cross-account duplicate IDs",
            "events=[{'id':'shared','account':'a','seq':1,'kind':'credit','amount':5},"
            "{'id':'shared','account':'b','seq':1,'kind':'credit','amount':90},"
            "{'id':'b1','account':'b','seq':2,'kind':'credit','amount':3}]\n"
            "r=solution(events)\n"
            "assert r['a']['balance']==5\n"
            "assert r['b']['balance']==0 and r['b']['next_seq']==1\n"
            "assert r['b']['pending_event_ids']==['b1']",
            weight=3,
        ),
        HiddenTest(
            "input immutability",
            "import copy\n"
            "events=[{'id':'m2','account':'m','seq':2,'kind':'credit','amount':2},"
            "{'id':'m1','account':'m','seq':1,'kind':'credit','amount':1}]\n"
            "before=copy.deepcopy(events)\nsolution(events)\nassert events==before",
        ),
        HiddenTest("empty stream", "assert solution([])=={}"),
    ),
)


_ROLLOUT_PLANNER = Challenge(
    id="rollout_planner",
    title="Dependency Rollout Planner",
    difficulty="Expert",
    prompt=(
        "Implement a deterministic deployment planner with this exact signature:\n\n"
        "    def plan_rollout(services: list[dict]) -> dict\n\n"
        "Each service has a unique `name`, a `depends_on` list, and integer "
        "`priority` where larger numbers deploy first when otherwise eligible.\n\n"
        "Return `{'stages': list[list[str]], 'blocked': list[str]}`. Every service "
        "in a stage must have all dependencies in earlier stages. Within a stage, "
        "sort by descending priority, then name. A service is blocked when it has "
        "a missing dependency, belongs to a dependency cycle, or transitively "
        "depends on any blocked service. Sort `blocked` alphabetically. Do not "
        "mutate the input. Empty input returns empty stages and blocked lists."
    ),
    test_cases=(
        HiddenTest(
            "linear dependency chain",
            "services=[{'name':'api','depends_on':['db'],'priority':5},"
            "{'name':'db','depends_on':[],'priority':1},"
            "{'name':'web','depends_on':['api'],'priority':9}]\n"
            "assert solution(services)=={'stages':[['db'],['api'],['web']],"
            "'blocked':[]}",
            weight=2,
        ),
        HiddenTest(
            "parallel priority and name ordering",
            "services=[{'name':'z','depends_on':[],'priority':2},"
            "{'name':'a','depends_on':[],'priority':2},"
            "{'name':'m','depends_on':[],'priority':8}]\n"
            "assert solution(services)['stages']==[['m','a','z']]",
            weight=2,
        ),
        HiddenTest(
            "missing dependency blocks transitively",
            "services=[{'name':'api','depends_on':['ghost'],'priority':5},"
            "{'name':'web','depends_on':['api'],'priority':9},"
            "{'name':'db','depends_on':[],'priority':1}]\n"
            "assert solution(services)=={'stages':[['db']],"
            "'blocked':['api','web']}",
            weight=3,
        ),
        HiddenTest(
            "cycle members and dependents are blocked",
            "services=[{'name':'a','depends_on':['b'],'priority':1},"
            "{'name':'b','depends_on':['a'],'priority':1},"
            "{'name':'c','depends_on':['a'],'priority':5},"
            "{'name':'free','depends_on':[],'priority':0}]\n"
            "assert solution(services)=={'stages':[['free']],"
            "'blocked':['a','b','c']}",
            weight=4,
        ),
        HiddenTest(
            "mixed graph uses earliest valid stages",
            "services=[{'name':'core','depends_on':[],'priority':1},"
            "{'name':'audit','depends_on':['core'],'priority':2},"
            "{'name':'api','depends_on':['core'],'priority':9},"
            "{'name':'web','depends_on':['api','audit'],'priority':4},"
            "{'name':'docs','depends_on':[],'priority':0}]\n"
            "assert solution(services)['stages']=="
            "[['core','docs'],['api','audit'],['web']]",
            weight=3,
        ),
        HiddenTest(
            "self dependency is a cycle",
            "services=[{'name':'loop','depends_on':['loop'],'priority':10}]\n"
            "assert solution(services)=={'stages':[],'blocked':['loop']}",
            weight=2,
        ),
        HiddenTest(
            "input immutability",
            "import copy\nservices=[{'name':'b','depends_on':['a'],'priority':1},"
            "{'name':'a','depends_on':[],'priority':2}]\n"
            "before=copy.deepcopy(services)\nsolution(services)\nassert services==before",
        ),
        HiddenTest(
            "empty service catalog",
            "assert solution([])=={'stages':[],'blocked':[]}",
        ),
    ),
)


_CONFIG_OVERLAY = Challenge(
    id="config_overlay",
    title="Configuration Overlay Engine",
    difficulty="Hard",
    prompt=(
        "Implement an immutable configuration overlay engine with this exact "
        "signature:\n\n"
        "    def apply_config(base: dict, overlays: list[dict]) -> dict\n\n"
        "Apply overlays from left to right. Ordinary dictionaries merge "
        "recursively. Scalars, `None`, and lists replace the previous value. The "
        "exact one-key directive `{'$delete': True}` deletes its key; deleting a "
        "missing key is a no-op. The exact one-key directive `{'$append': [...]}` "
        "appends to an existing list, or creates a new list when the key is "
        "missing. Directive-shaped dictionaries with extra keys are ordinary "
        "data and merge normally. Do not mutate `base`, `overlays`, or nested "
        "values."
    ),
    test_cases=(
        HiddenTest(
            "recursive merge preserves siblings",
            "base={'db':{'host':'a','port':5432},'debug':False}\n"
            "overlays=[{'db':{'host':'b'}}]\n"
            "assert solution(base,overlays)=="
            "{'db':{'host':'b','port':5432},'debug':False}",
            weight=2,
        ),
        HiddenTest(
            "lists replace by default",
            "assert solution({'tags':['a','b']},[{'tags':['c']}])=={'tags':['c']}",
            weight=2,
        ),
        HiddenTest(
            "nested deletion",
            "base={'service':{'host':'x','secret':'gone'},'keep':1}\n"
            "overlays=[{'service':{'secret':{'$delete':True}}}]\n"
            "assert solution(base,overlays)=={'service':{'host':'x'},'keep':1}",
            weight=3,
        ),
        HiddenTest(
            "append existing and missing lists",
            "base={'plugins':['core']}\n"
            "overlays=[{'plugins':{'$append':['audit']}},"
            "{'regions':{'$append':['eu','us']}}]\n"
            "assert solution(base,overlays)=="
            "{'plugins':['core','audit'],'regions':['eu','us']}",
            weight=3,
        ),
        HiddenTest(
            "overlay order changes meaning",
            "base={'items':[1]}\n"
            "overlays=[{'items':{'$append':[2]}},{'items':[9]},"
            "{'items':{'$append':[10]}}]\n"
            "assert solution(base,overlays)=={'items':[9,10]}",
            weight=3,
        ),
        HiddenTest(
            "directives require an exact shape",
            "base={}\noverlays=[{'data':{'$delete':True,'reason':'audit'},"
            "'more':{'$append':[1],'note':'data'}}]\n"
            "assert solution(base,overlays)=={'data':{'$delete':True,'reason':'audit'},"
            "'more':{'$append':[1],'note':'data'}}",
            weight=3,
        ),
        HiddenTest(
            "none is a normal replacement value",
            "assert solution({'timeout':30},[{'timeout':None}])=={'timeout':None}",
        ),
        HiddenTest(
            "deep input immutability",
            "import copy\nbase={'a':{'items':[1]}}\n"
            "overlays=[{'a':{'items':{'$append':[2]}}}]\n"
            "base_before=copy.deepcopy(base)\noverlays_before=copy.deepcopy(overlays)\n"
            "result=solution(base,overlays)\nresult['a']['items'].append(3)\n"
            "assert base==base_before and overlays==overlays_before",
            weight=2,
        ),
        HiddenTest(
            "empty overlays return a deep copy",
            "base={'nested':{'values':[1]}}\nr=solution(base,[])\n"
            "r['nested']['values'].append(2)\n"
            "assert base=={'nested':{'values':[1]}}",
        ),
    ),
)


PRESETS: list[Challenge] = [
    _EVENT_RECONCILER,
    _ROLLOUT_PLANNER,
    _CONFIG_OVERLAY,
    _TWO_SUM,
    _VALID_PARENS,
    _LRU_CACHE,
    _MERGE_INTERVALS,
]


def by_id(challenge_id: str) -> Challenge:
    for c in PRESETS:
        if c.id == challenge_id:
            return c
    raise KeyError(challenge_id)
