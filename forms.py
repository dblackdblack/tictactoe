from __future__ import unicode_literals

import string

from sqlalchemy.orm.exc import NoResultFound

import tictactoe
from flask_wtf import Form
from wtforms import StringField
from wtforms.validators import DataRequired, ValidationError, Length

MAX_USERNAME_LENGTH = 50


class LoginForm(Form):
    username = StringField(
        'username', validators=(DataRequired(),
                                Length(max=MAX_USERNAME_LENGTH)))

    def validate_username(self, field):
        valid_username_chars = string.letters + string.digits + '-_'
        if any(c for c in field.data if c not in valid_username_chars):
            raise ValidationError("username contains invalid an invalid "
                                  "character.")
        try:
            tictactoe.User.query.filter_by(username=field.data).one()
        except NoResultFound:
            raise ValidationError("invalid username '%s'" % field.data)


class NewUserForm(Form):
    username = StringField(
        'username', validators=(DataRequired(),
                                Length(max=MAX_USERNAME_LENGTH)))

    def validate_username(self, field):
        valid_username_chars = string.letters + string.digits + '-_'
        if any(c for c in field.data if c not in valid_username_chars):
            raise ValidationError("username contains invalid an invalid "
                                  "character.")

        if tictactoe.User.query.filter_by(
                username=field.data).limit(1).scalar():
            raise ValidationError("username '%s' already exists" % field.data)

