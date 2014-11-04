from __future__ import unicode_literals

from sqlalchemy.orm.exc import NoResultFound

from tictactoe import User
from flask_wtf import Form
from wtforms import StringField
from wtforms.validators import DataRequired, ValidationError, Length

MAX_USERNAME_LENGTH = 50


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