
import itertools as it
import random
import collections
from functools import partial

class IllegalPlay(ValueError): pass
class GameOver(Exception): pass

BONES_PER_HAND = 7 # standard number of dominoes in a starting hand

def generate_dominoes(size):
    for i in range(size+1):
        for j in range(i+1):
            yield (j, i) # i is always >= j
    return

assert len(list(generate_dominoes(6))) == 28
assert len(set(generate_dominoes(6))) == 28
assert len(list(generate_dominoes(9))) == 55
assert len(set(generate_dominoes(9))) == 55
assert len(list(generate_dominoes(12))) == 91
assert len(set(generate_dominoes(12))) == 91

def pair_to_domino(a, b):
    ''' return a domino object (a tuple) made from the a/b pair '''
    return tuple(sorted([a, b]))

def pairs_and_reverse(hand):
    for a, b in hand:
        yield a, b
        yield b, a
    return

def hand_sum(hand):
    tot = 0
    for x, y in hand:
        tot += x + y
    return tot

class Muggins(object):
    def __init__(self, size=6):
        self.size = size
        self._boneyard = list(generate_dominoes(size))
        random.shuffle(self._boneyard)
        self.ends = []
        self.played = [] # [(player #, play_on, expose, drew, turn_score) ... ]
        self.visible = set() # dominos on the table
        self.scores = collections.defaultdict(int)
        self._players = [] # [(player_generator, hand) ... ]
        return

    def play(self, player_no, play_on, expose):
        ''' play_on is the value of the end you are attaching to.
            expose  is the value of the end you are leaving exposed.
            In the case of doubles (play_on == expose) two new ends are created
        '''
        domino = pair_to_domino(play_on, expose)

        if not self.played:
            pass
        elif play_on not in self.ends:
            raise IllegalPlay("that dangling node does not exist")
        elif domino not in self._players[player_no][1]:
            raise IllegalPlay("you do not have that to play")

        if play_on == expose or not self.played: # doubles or first tile
            self.ends.extend(domino)
        else:
            for pop_i, val in enumerate(self.ends):
                if play_on == val:
                    break
            self.ends.pop(pop_i)
            self.ends.append(expose)

        self._players[player_no][1].remove(domino)
        if sum(self.ends) % 5 == 0:
            turn_score = sum(self.ends)
        else:
            turn_score = 0

        self.played.append((player_no, play_on, expose, None, turn_score))
        self.visible.add(pair_to_domino(play_on, expose))
        self.scores[player_no] += turn_score

        if not self._players[player_no][1]:
            raise GameOver("player out of dominos")
        return turn_score

    def start(self):
        ''' determine which domino is played first, and then play it.
            We have to be VERY careful when deciding ties.  The player
            that goes second has an advantage so we can't favor one
            player over another just because they happen to be first or
            last in the _players array.
        '''
        all = [(-1, -1, -1)]
        for gen, hand in self._players:
            for a, b in hand:
                all.append((a+b, random.random(), a, b))
        all.sort()
        tot, dummy, a, b = all[-1]
        assert tot != -1
        for player_no, (gen, hand) in enumerate(self._players):
            if (a,b) in hand:
                break
        self.play(player_no, a, b)
        self._went_first = player_no
        return player_no

    def draw(self, player_no):
        if len(self._boneyard) <= 2:
            raise GameOver("boneyard empty")

        # check to make sure the player can't play
        for a, b in pairs_and_reverse(self._players[player_no][1]):
            try:
                self.play(player_no, a, b)
            except IllegalPlay:
                continue
            self.undo()
            raise IllegalPlay("you can play, so you can't draw")

        domino = self._boneyard.pop()
        self._players[player_no][1].add(domino)
        self.played.append((player_no, None, None, domino, 0))
        return domino

    def undo(self):
        player_no, play_on, expose, drew, turn_score = self.played.pop()
        if drew is not None:
            self._boneyard.append(drew)
            # NB, we DO NOT shuffle
            self._players[player_no].remove(drew)
        elif play_on == expose:
            self.ends.pop()
            self.ends.pop()
        elif expose == self.ends[-1]:
            self.ends.pop()
            self.ends.append(play_on)

        if drew is None:
            self.visible.remove(pair_to_domino(play_on, expose))
            self._players[player_no][1].add(pair_to_domino(play_on, expose))

        self.scores[player_no] -= turn_score
        return

    def join_game(self, score_func):
        hand = set()
        for _ in range(BONES_PER_HAND):
            hand.add(self._boneyard.pop())
        player_no = len(self._players)
        callable = generic_score(score_func)
        gen = callable(player_no, self, hand)
        gen.next() # advance past initialization
        self._players.append((gen, hand))
        return (player_no, hand)

    def run_game(self):
        if len(self._players) < 2:
            raise ValueError("Need at least two players!")

        players = self._players[:]
        random.shuffle(players)
        first_player = self.start()
        players = players[first_player+1:] + players[:first_player+1]
        #assert players[-1] == self._players[first_player]
        for gen, hand in it.cycle(players):
            played_cnt = len(self.played)
            try:
                gen.send(None)
                assert len(self.played) > played_cnt, self.played
            except GameOver:
                best_hand = 1000
                for gen, hand in players:
                    best_hand = min(best_hand, hand_sum(hand))

                leftover_points = 0
                for gen, hand in players:
                    if hand_sum(hand) == best_hand:
                        continue
                    hand_points = 0
                    for x, y in hand:
                        hand_points += x + y
                    # round up to nearest 5
                    if hand_points % 5:
                        hand_points += 5 - (hand_points % 5)
                    leftover_points += hand_points
                for player_no, (gen, hand) in enumerate(self._players):
                    if hand_sum(hand) == best_hand:
                        self.scores[player_no] += leftover_points
                break
        return self.scores

def run_tournament(*players):
    scores = collections.defaultdict(int)
    went_first = collections.defaultdict(int)
    for _ in range(10000):
        board = Muggins()
        for p in players:
            p_no, hand = board.join_game(p)
            assert len(board._players)
        _scores = board.run_game()
        went_first[board._went_first] += 1
        winning_score = max(_scores.values())
        for p_no, score in _scores.items():
            if score == winning_score:
                scores[p_no] += 1

    final = [(b,a) for (a,b) in scores.items()]
    final.sort(reverse=True)
    for k, v in final:
        print k, v, players[v].__name__
    print ''
    return players[final[0][1]]

def round_robin(*players):
    ''' like run_tournament but run each player against each player '''
    wins = collections.defaultdict(list)
    for p1, p2 in it.combinations(players, 2):
        winner = run_tournament(p1, p2)
        wins[winner].append(p1 if winner == p2 else p2)
    for k, v in wins.items():
        print k.__name__, "beat", len(v), [f.__name__ for f in v]
    return

def dumb_player(player_no, board, hand):
    ''' a player that just plays the first domino that is legal '''
    yield None
    while True:
        for a, b in pairs_and_reverse(hand):
            try:
                board.play(player_no, a, b)
                yield None
                break
            except IllegalPlay: pass
        else:
            board.draw(player_no)
    return

def score_player(player_no, board, hand):
    ''' a player that plays whatever domino is immediately highest scoring '''
    yield None
    while True:
        best = (-1, None, None) # (score, domino)
        for a, b in pairs_and_reverse(hand):
            try:
                sc = board.play(player_no, a, b)
                best = max(best, (sc, a, b))
                board.undo()
            except IllegalPlay: pass

        sc, a, b = best
        if sc == -1: # can't play
            board.draw(player_no)
        else: # we have a good move
            board.play(player_no, a, b)
            yield None
    return

def generic_score(score_func):
    def _player(player_no, board, hand):
        yield None
        while True:
            best = None
            cache = {}
            for a, b in pairs_and_reverse(hand):
                if a in board.ends:
                    sc = score_func(board, player_no, a, b, cache)
                    best = max(best, (sc, random.random(), a, b))
            if best == None:
                board.draw(player_no)
            else:
                a, b = best[-2:]
                board.play(player_no, a, b)
                yield None
        return
    _player.__name__ = score_func.__name__
    return _player

def dumb_player2(board, player_no, a, b, cache):
    ''' a player that randomly chooses a legal play '''
    return None

def dumb_player(board, player_no, a, b, cache):
    ''' a player that randomly chooses a legal play '''
    return b-a

def score_player2(board, player_no, a, b, cache):
    sc = board.play(player_no, a, b)
    board.undo()
    return (sc, b-a)

def score_blocker2(board, player_no, a, b, cache):
    sc = board.play(player_no, a, b)
    unq_ends = len(set(board.ends))
    board.undo()
    return (sc, -unq_ends, b-a)

def score_blocker3(board, player_no, a, b, cache):
    sc = board.play(player_no, a, b)
    all_ends = len(board.ends)
    board.undo()
    return (sc, -all_ends, b-a)

def score_player3(board, player_no, a, b, cache):
    sc = board.play(player_no, a, b)
    board.undo()
    return sc

def score_blocker6(board, player_no, a, b, cache):
    if not cache:
        d = cache['counts'] = collections.defaultdict(int)
        for x, y in board.visible:
            d[x] += 1
            d[y] += 1
        hand = board._players[player_no][1] # our hand
    else:
        d = cache['counts']

    sc = board.play(player_no, a, b)
    board.undo()
    return (sc, d[b]-d[a])

def score_blocker5(board, player_no, a, b, cache):
    if not cache:
        d = cache['counts'] = collections.defaultdict(int)
        for x, y in board.visible:
            d[x] += 1
            d[y] += 1
        hand = board._players[player_no][1] # our hand
        for x, y in hand:
            d[x] -= 1
            d[y] -= 1
    else:
        d = cache['counts']

    sc = board.play(player_no, a, b)
    board.undo()
    return (sc, d[b]-d[a])

if __name__ == '__main__':
    round_robin(score_blocker2,
                score_blocker3,
                score_blocker5,
                score_blocker6,
                score_player3,
                score_player2,
                dumb_player2,
                dumb_player,
               )

