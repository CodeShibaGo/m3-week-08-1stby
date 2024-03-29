from flask import render_template, flash, redirect, url_for, request, session
from urllib.parse import urlsplit
from flask_login import login_user, logout_user, current_user
import sqlalchemy as sa
from app import  db
from app.auth import bp
from app.auth.forms import ResetPasswordRequestForm, ResetPasswordForm
from app.models import User
from app.auth.email import send_password_reset_email
from sqlalchemy import text
from werkzeug.security import check_password_hash, generate_password_hash
from flask_wtf.csrf import generate_csrf



@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        sql = text("SELECT * FROM user WHERE username = :username LIMIT 1")
        result = db.session.execute(sql, {'username':username}).fetchone()
        
        if result:
            user = User(
                id=result.id,
                username=result.username,
                email=result.email,
                password_hash=result.password_hash
            )
            if check_password_hash(user.password_hash, password):
                login_user(user)
                session['logged_in'] = True
                session['username'] = username
                return redirect(url_for('main.index'))
            else:
                flash('密碼錯誤')
                return redirect(url_for('auth.login'))
        else:
            flash('使用者名稱不存在')
            return redirect(url_for('auth.login'))

    return render_template('auth/login.html', title='Sign In', csrf_token=generate_csrf)

@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        password2 = request.form['password2']

        #檢查是否有相同的 username or email
        sql = text('SELECT * FROM user WHERE username = :username OR email = :email')
        result = db.session.execute(sql, {'username':username, 'email':email}).fetchone()

        if result:
            flash('使用者已存在')
            return redirect(url_for('auth.register'))

        if password != password2:
            flash('密碼不一致')
            return redirect(url_for('auth.register'))

        # 創建新使用者
        hashed_password = generate_password_hash(password)
        sql = text('INSERT INTO user (username, email, password_hash) VALUES (:username, :email, :password_hash)')
        db.session.execute(sql, {'username': username, 'email': email, 'password_hash': hashed_password})  
        db.session.commit()

        flash('註冊成功')    
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', title='Register', csrf_token=generate_csrf())

@bp.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.email == form.email.data))
        if user:
            send_password_reset_email(user)
        flash('請檢查你的電子郵件以獲取重設密碼的指示')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password_request.html',
                           title='重設密碼', form=form)

@bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('main.index'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been reset.')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', form=form)