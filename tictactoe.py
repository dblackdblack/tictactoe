#!/usr/bin/env python

from __future__ import unicode_literals

import os
import copy
import json
import os.path
import datetime
import itertools

import pytz
from concurrent import futures

from sqlalchemy import desc
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.schema import ForeignKey

from flask import (Flask, flash, redirect, url_for, render_template, request,
                   session, abort)
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.login import (LoginManager, login_user, logout_user,
                             login_required, current_user)

MAX_USERNAME_LENGTH = 50

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = ''.join((
    'sqlite:///',
    os.path.join(os.environ['TICTACTOE_ROOT'], 'tictactoe.db')
))

# XXX obvs this should not be in here...move to an env var or settings file
app.secret_key = 'NLRPwu/hhUQMZ9\dD6RI-Oma?WSNnG%.,.`Olr47'
app.debug = True

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)

EMPTY_GAME = ((None,) * 3, (None,) * 3, (None,) * 3)


# --------- Views ------------


@app.route('/', methods=('GET',))
@login_required
def tictactoe():
    return render_template('index.html', logout_url=url_for('logout'),
                           username=current_user.username)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route("/login", methods=("GET", "POST"))
def login():
    form = LoginForm()  # LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.data['username']).one()
        login_user(user)
        flash("Logged in successfully.")
        return redirect(request.args.get("next") or url_for("tictactoe"))

    return render_template("login.html", form=form,
                           new_user_url=url_for('new_user'))


@app.route('/new_user', methods=('GET', 'POST'))
def new_user():
    form = NewUserForm()
    if form.validate_on_submit():
        user = User(username=form.data['username'])
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Thanks!!!!")
        return redirect(request.args.get("next") or url_for("tictactoe"))

    return render_template("new_user.html", form=form,
                           login_url=url_for('login'))


@app.route('/latest_game', methods=('GET',))
@login_required
def latest_game():
    game = current_user.latest_game()
    if game:
        result = game.get_cell_list()
        return game.json_status()

    else:
        result = EMPTY_GAME
        return json.dumps({'cells': result, 'status': 'new'})


# XXX add CSRF checking
@app.route('/cell_click', methods=('POST',))
@login_required
def cell_click():
    req_data = json.loads(request.data)
    x, y = req_data['x'], req_data['y']
    game = current_user.latest_game() or Game.new_game(user_id=current_user.id)

    if game.is_valid_move(x, y):
        if _is_in_won_state(board_state=game.get_cell_list()):
            raise ValidationError('this game has already been won')

        game.add_move(x=x, y=y, player='x')

        winner = _is_in_won_state(board_state=game.get_cell_list())
        if winner and winner == 'tie':
            game.change_status(status='tie')
        elif winner:
            game.change_status(status='won', player='x')
            flash("you win!")

        else:
            move = game.minimax_move(computer_player='o')
            game.add_move(x=move[0], y=move[1], player='o')

            winner = _is_in_won_state(board_state=game.get_cell_list())
            if winner and winner == 'tie':
                game.change_status(status='tie', player=None)
            elif winner:
                game.change_status(status='won', player=winner)
                flash("computer wins!")

    else:
        abort(403)

    return game.json_status()

@app.route('/new_game', methods=('POST',))
@login_required
def new_game():
    game = Game.new_game(user_id=current_user.id)
    return game.json_status()


@login_manager.unauthorized_handler
def unauthorized():
    return redirect(url_for('login'))


# --------- ORM Objects -------------


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(MAX_USERNAME_LENGTH), unique=True)
    games = db.relationship('Game', backref='user', lazy='dynamic')

    def __init__(self, username):
        self.username = username

    def __repr__(self):
        return "<User %r>" % self.username

    def is_authenticated(self):
        if User.query.filter_by(username=self.username).one():
            return True
        return False

    def is_anonymous(self):
        return False

    def is_active(self):
        return True

    def get_id(self):
        return self.username

    @staticmethod
    @login_manager.user_loader
    def load_user(userid):
        return User.query.filter_by(username=userid).limit(1).scalar()

    def latest_game(self):
        try:
            return Game.query.filter_by(
                user_id=self.id
            ).order_by(
                desc(Game.ctime)
            )[0]

        except IndexError:
            return None


class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(User.id), index=True,
                        nullable=False)
    status = db.Column(db.String(10), index=True)
    cells = db.relationship('CellState', backref='game')
    ctime = db.Column(db.DateTime, default=lambda: utcnow())
    winner = db.Column(db.String(len('tie')))

    VALID_CELL_STATES = ('x', 'o')

    def get_cell_list(self):
        result = [[None] * 3, [None] * 3, [None] * 3]
        for cell in self.cells:
            state = cell.state
            if state not in Game.VALID_CELL_STATES:
                raise ValidationError("invalid cell state %s" % state)

            result[cell.x][cell.y] = cell.state
        return result

    def is_valid_move(self, x, y):
        if self.status not in ('new', 'in_progress'):
            return False

        try:
            _ = CellState.query.filter_by(game_id=self.id, x=x, y=y)[0]
            return False
        except IndexError:
            return True

    def add_move(self, x, y, player):
        if player not in self.VALID_CELL_STATES:
            raise ValidationError("invalid player %s" % player)
        if CellState.query.filter_by(
                game_id=self.id, x=x, y=y).limit(1).scalar():
            # this shouldn't happen b/c is_valid_move should prevent attempted
            # add move of a location which already has a cell
            raise Exception("there is already a cell at x=%s y=%s" % (x, y))
        new_move = CellState(game_id=self.id, x=x, y=y, state=player)
        db.session.add(new_move)

        if self.status == 'new':
            self.status = 'in_progress'
            db.session.add(self)

        db.session.commit()

    @classmethod
    def new_game(cls, user_id):
        game = Game(user_id=user_id, status='new')
        db.session.add(game)
        db.session.commit()
        return game

    def change_status(self, status, player=None):
        if self.status == status:
            return

        self.status = status
        if status == 'won':
            self.winner = player

        db.session.add(self)
        db.session.commit()

    def json_status(self):
        return json.dumps({'cells': self.get_cell_list(),
                           'status': self.status})

    # http://www.neverstopbuilding.com/minimax
    def minimax_move(self, computer_player):
        current_state = self.get_cell_list()

        # if this if the first time the computer is making a move, look up
        # the optimal move from a table rather than calculating it.
        # Calculating the computer's first move is by far the slowest
        # calculation, so caching this result should make things much more
        # pleasant for the user waiting for the computer to make its move
        avail_moves = _available_moves(current_state=current_state)
        if len(avail_moves) == 8:
            return _get_best_second_move(current_state)

        # perform the minimax calculation by using threads.  This actually
        # makes the calculation slower (versus single thread) on my laptop
        # b/c the minimax descent is mostly bounded by RAM I/O bandwidth, not
        # by CPU cycles, so having more threads competing for RAM bandwidth
        # just means there are more context switches.  On a beefier system with
        # more RAM throughput, we might actually gain something by bringing
        # more CPUs to bear on the problem
        myfutures = {}
        with futures.ThreadPoolExecutor(max_workers=5) as executor:
            for move in avail_moves:
                possible_state = copy.deepcopy(current_state)
                possible_state[move[0]][move[1]] = computer_player
                myfutures[move] = executor.submit(
                    _minimax,
                    current_state=possible_state,
                    computer_player=computer_player,
                    current_player=_other_player(computer_player)
                )

        # get max result and return the move which produces this result
        return sorted(myfutures.keys(), key=lambda x: myfutures[x].result(),
                      reverse=True)[0]


class CellState(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey(Game.id), index=True,
                        nullable=False)
    x = db.Column(db.Integer, nullable=False)
    y = db.Column(db.Integer, nullable=False)
    state = db.Column(db.CHAR)

    @property
    def user(self):
        return self.game.user

# ------- FORMS ----------

from flask_wtf import Form
from wtforms import StringField
from wtforms.validators import DataRequired, ValidationError, Length


class LoginForm(Form):
    username = StringField(
        'username', validators=(DataRequired(),
                                Length(max=MAX_USERNAME_LENGTH)))

    def validate_username(self, field):
        try:
            User.query.filter_by(username=field.data).one()
        except NoResultFound:
            raise ValidationError("invalid username '%s'" % field.data)


class NewUserForm(Form):
    username = StringField(
        'username', validators=(DataRequired(),
                                Length(max=MAX_USERNAME_LENGTH)))

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).limit(1).scalar():
            raise ValidationError("username '%s' already exists" % field.data)

# ------- Utility functions -----------


def utcnow():
    return datetime.datetime.now().replace(tzinfo=pytz.utc)


def _other_player(current_player):
        if current_player == 'x':
            return 'o'
        return 'x'


def _get_best_second_move(first_move_state):
        # after the human player has taken the first move, we want the computer
        # to make the second move.  Calculating the best possible
        # move takes 5-8 sec on my quad core laptop and is easily
        # pre-calculable, so hard-code the correct followup move for the 9
        # possible first moves. All subsequent moves have much smaller decision
        # spaces, so perform best move calculation for the 4rd, 6th, and 8th
        # moves rather than hard-coding

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


def _is_in_won_state(board_state):
    winners = (  # list all winning board states for a particular player
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

    x_won = any(
        state for state in winners
        if _state_matches(state, player='x', board_state=board_state))

    o_won = any(
        state for state in winners
        if _state_matches(state, player='o', board_state=board_state))

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
    else:
        return


def _minimax(current_state, computer_player, current_player):
    winner = _is_in_won_state(board_state=current_state)

    if winner == computer_player:
        return 1
    elif winner == 'tie':
        return 0
    elif winner and winner != computer_player:
        return -1
    else:  # no winner yet, which is fine
        pass

    scores = []
    for move in _available_moves(current_state=current_state):
        possible_state = copy.deepcopy(current_state)
        possible_state[move[0]][move[1]] = current_player
        next_player = _other_player(current_player)
        scores.append(_minimax(current_state=possible_state,
                              computer_player=computer_player,
                              current_player=next_player))

    if current_player == computer_player:
        return max(scores)
    else:
        return min(scores)


def _available_moves(current_state):
    all_locations = itertools.product(xrange(3), xrange(3))
    moves = (location for location in all_locations
             if current_state[location[0]][location[1]] is None)
    return list(moves)


def _state_matches(state, player, board_state):
    return all(board_state[cell[0]][cell[1]] == player for cell in state)

if __name__ == '__main__':
    app.run()