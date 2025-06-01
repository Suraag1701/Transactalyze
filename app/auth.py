from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required
from .models import User
from . import db

auth = Blueprint('auth', __name__)


@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if User.query.filter_by(email=email).first():
            flash('Email already registered.')
            return redirect(url_for('auth.signup'))

        new_user = User(email=email,
                        password_hash=generate_password_hash(password,
                                                             method='sha256'))
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully. Please log in.')
        return redirect(url_for('auth.login'))

    return render_template('signup.html')


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash('Invalid credentials')
            return redirect(url_for('auth.login'))

        login_user(user)
        return redirect(url_for('main.index'))

    return render_template('login.html')


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))
