from __future__ import unicode_literals

import copy
import datetime
import itertools

import pytz


def utcnow():
    return datetime.datetime.now().replace(tzinfo=pytz.utc)


def other_player(current_player):
    if current_player == 'x':
        return 'o'
    return 'x'


# after the human player has taken the first move, we want the computer
# to make the second move.  Calculating the best possible move takes 5-8 sec
# on my quad core laptop and is easily pre-calculable, so, to save time,
# hard-code the correct followup move for all 9 possible first moves.
def get_best_second_move(first_move_state):
    # iterate over the whole board and pick the one occupied spot as
    # being the first move
    all_locations = itertools.product(xrange(3), xrange(3))
    first_move = (
        location for location in all_locations
        if first_move_state[location[0]][location[1]]
    ).next()

    # look up the correct counter move in this dict
    second_move_lookup = {
        (0, 0): (1, 1),
        (2, 0): (1, 1),
        (0, 2): (1, 1),
        (2, 2): (1, 1),

        (0, 1): (0, 0),
        (2, 1): (0, 1),
        (1, 0): (1, 2),
        (1, 2): (1, 1),

        (1, 1): (0, 0),
    }

    return second_move_lookup[first_move]


# enumerate all sequences of moves which would mean that a player has won
# e.g. if the player has made moves (0,0), (1, 0), (2, 0), this would be the
# top-most horizontal line on the board.  If a player had all three of these
# moves, that player must have won
WINNING_STATES = (
    # horizontal
    ((0, 0), (1, 0), (2, 0)),
    ((0, 1), (1, 1), (2, 1)),
    ((0, 2), (1, 2), (2, 2)),

    # vertical
    ((0, 0), (0, 1), (0, 2)),
    ((1, 0), (1, 1), (1, 2)),
    ((2, 0), (2, 1), (2, 2)),

    # diagonal
    ((0, 0), (1, 1), (2, 2)),
    ((2, 0), (1, 1), (0, 2)),
)


# return which player ('x' or 'o') is the winner, 'tie' if the game has ended
# in a tie, or None if there is no winner yet
def get_winner(board_state):
    # list all winning board states for a particular player
    x_won = any(
        state for state in WINNING_STATES
        if state_matches(state, player='x', board_state=board_state)
    )

    o_won = any(
        state for state in WINNING_STATES
        if state_matches(state, player='o', board_state=board_state)
    )

    # iterate over all locations on the board, and if there are no empty
    # locations, then the board is full (board_full=True)
    all_locations = itertools.product(xrange(3), xrange(3))
    board_full = not any(
        location for location in all_locations
        if board_state[location[0]][location[1]] is None
    )

    if x_won:
        return 'x'
    elif o_won:
        return 'o'
    elif board_full:
        return 'tie'
    else:  # no winner yet
        return


# used in conjunction with _is_in_won_state to determine whether the
# passed-in player has played all the cells locations in state.  This
# is used to determine if a player has won the game by matching against
# all possible winning moves, as enumerated in WINNING_STATES
def state_matches(state, player, board_state):
    return all(board_state[cell[0]][cell[1]] == player for cell in state)


# the minimax algorithm for playing perfect information games
# http://web.stanford.edu/~msirota/soco/minimax.html
def minimax(current_state, computer_player, current_player):
    winner = get_winner(board_state=current_state)
    if winner:
        return minimax_score(winner=winner, computer_player=computer_player)

    scores = []
    for move in get_available_moves(current_state=current_state):
        possible_state = apply_move(initial_state=current_state,
                                    move=move,
                                    current_player=current_player)
        next_player = other_player(current_player)
        scores.append(minimax(current_state=possible_state,
                              computer_player=computer_player,
                              current_player=next_player))

    if current_player == computer_player:
        return max(scores)
    else:
        return min(scores)


# called on games which have ended in a win or a tie
# returns 1 if the computer has won, 0 if tie, -1 if human won
def minimax_score(winner, computer_player):
    if winner == computer_player:
        return 1
    elif winner == 'tie':
        return 0
    elif winner and winner != computer_player:
        return -1
    else:  # this shouldn't get called unless there's a winner
        raise NotImplemented("shouldn't get here")


# make a copy of initial_state and apply a move made by current_player to
# that state.  Used to recursively descending the possibility space by minimax
def apply_move(initial_state, move, current_player):
    next_state = copy.deepcopy(initial_state)
    next_state[move[0]][move[1]] = current_player
    return next_state


# iterate over all locations on the board and return list of all empty cells
def get_available_moves(current_state):
    all_locations = itertools.product(xrange(3), xrange(3))
    moves = (location for location in all_locations
             if current_state[location[0]][location[1]] is None)
    return list(moves)