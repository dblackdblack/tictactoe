#!/usr/bin/env python

from __future__ import unicode_literals

import os
import json
import os.path

from concurrent import futures

from sqlalchemy import desc
from flask import (Flask, flash, redirect, url_for, render_template, request,
                   abort)
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.login import (LoginManager, login_user, logout_user,
                             login_required, current_user)
from wtforms.validators import ValidationError

import forms
from utils import (utcnow, get_winner, get_available_moves,
                   get_best_second_move, apply_move, minimax, other_player)

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
    form = forms.LoginForm()  # LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.data['username']).one()
        login_user(user)
        flash("Logged in successfully.")
        return redirect(request.args.get("next") or url_for("tictactoe"))

    return render_template("login.html", form=form,
                           new_user_url=url_for('new_user'))


@app.route('/new_user', methods=('GET', 'POST'))
def new_user():
    form = forms.NewUserForm()
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
        if get_winner(board_state=game.get_cell_list()):
            raise ValidationError('this game has already been won')

        game.add_move(x=x, y=y, player='x')

        # after applying the human's move, check to see if the board is now
        # in a won/tied state
        winner = get_winner(board_state=game.get_cell_list())
        if winner and winner == 'tie':
            game.change_status(status='tie')

        elif winner:  # state just changed from not-won => won after
                      # applying the human's move, so the human must have won
            human_won(game)

        else:  # no winner after human's move, so kick off computer's move
            computer_move(game)

    else:
        abort(403)

    return game.json_status()


def human_won(game):
    game.change_status(status='won', player='x')
    flash("you win!")

    # if the minimax algorithm is written correctly, the human player
    # should never win.  The best s/he can do is tie
    raise Exception("The human must never win")


def computer_move(game):
    move = game.minimax_move(computer_player='o')
    game.add_move(x=move[0], y=move[1], player='o')

    winner = get_winner(board_state=game.get_cell_list())
    if winner and winner == 'tie':
        game.change_status(status='tie', player=None)

    elif winner:  # game changed from not-won => won after computer's
                  # move, so computer must have won
        game.change_status(status='won', player=winner)
        flash("computer wins!")


@app.route('/new_game', methods=('POST',))
@login_required
def new_game():
    game = Game.new_game(user_id=current_user.id)
    return game.json_status()


@login_manager.unauthorized_handler
def unauthorized():
    return redirect(url_for('login'))


# --------- ORM Objects/Models -------------


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

        # does this cell exist in the database already?  If so, invalid move
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

    # inspired by http://www.neverstopbuilding.com/minimax
    def minimax_move(self, computer_player):
        current_state = self.get_cell_list()

        # if this if the first time the computer is making a move, look up
        # the optimal move from a table rather than calculating it.
        # Calculating the computer's first move is by far the slowest
        # calculation, so caching this result should make things much more
        # pleasant for the user waiting for the computer to make its move
        avail_moves = get_available_moves(current_state=current_state)
        if len(avail_moves) == 8:
            return get_best_second_move(current_state)

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
                possible_state = apply_move(initial_state=current_state,
                                             current_player=computer_player,
                                             move=move)
                myfutures[move] = executor.submit(
                    minimax,
                    current_state=possible_state,
                    computer_player=computer_player,
                    current_player=other_player(computer_player)
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


if __name__ == '__main__':
    app.run()