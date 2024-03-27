from datetime import datetime, timezone
from urllib.parse import urlsplit
from flask import render_template, flash, redirect, url_for, request, session
from flask_login import login_user, logout_user, current_user, login_required
from flask_wtf.csrf import generate_csrf
import sqlalchemy as sa
from app import app, db
from app.forms import LoginForm, RegistrationForm, EditProfileForm, EmptyForm, PostForm, ResetPasswordRequestForm, ResetPasswordForm
from app.models import User, Post
from app.email import send_password_reset_email
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import text

@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    form = PostForm()
    if form.validate_on_submit():
        post_body = form.post.data
        user_id = current_user.id
        timestamp = datetime.now(timezone.utc)
        sql = text("INSERT INTO post (body, user_id, timestamp)  VALUES (:body, :user_id, :timestamp)")
        db.session.execute(sql, {'body': post_body, 'user_id': user_id, 'timestamp':timestamp})
        db.session.commit()
        flash('你的貼文現在已發布！')
        return redirect(url_for('index'))
    
    page = request.args.get('page', 1, type=int)
    per_page = app.config['POSTS_PER_PAGE']
    offset = (page - 1) * per_page

    sql = text("""
        SELECT * FROM post
        JOIN followers ON followers.followed_id = post.user_id
        JOIN user ON user.id = post.user_id
        WHERE followers.followed_id = :current_user_id
        ORDER BY post.timestamp DESC
        LIMIT :per_page OFFSET :offset
    """)
    result = db.session.execute(sql, {'current_user_id': current_user.id, 'per_page': per_page, 'offset': offset})

    posts = []
    for row in result:
        post = {
            'id': row.id,
            'body': row.body,
            'timestamp': row.timestamp,
            'user_id': row.user_id,
            'author': {
                'username': row.username,
                'avatar': User(email=row.email).avatar(70) 
            }
        }
        posts.append(post)

    sql_count = text("""
        SELECT COUNT(*) FROM post
        JOIN followers ON followers.followed_id = post.user_id
        WHERE followers.follower_id = :current_user_id
    """)
    total_posts = db.session.execute(sql_count, {'current_user_id': current_user.id}).scalar()

    has_next = page * per_page < total_posts
    has_prev = page > 1
    next_url = url_for('index', page=page+1) if has_next else None
    prev_url = url_for('index', page=page-1) if has_prev else None

    return render_template('index.html', title='首頁', form=form,
                           posts=posts, next_url=next_url, prev_url=prev_url)

@app.route('/explore')
@login_required
def explore():
    page = request.args.get('page', 1, type=int)
    per_page = app.config['POSTS_PER_PAGE']
    offset = (page - 1) * per_page

    sql = text("""
        SELECT * FROM post
        JOIN user ON post.user_id = user.id
        ORDER BY post.timestamp DESC
        LIMIT :per_page OFFSET :offset
    """)
    result = db.session.execute(sql, {'per_page': per_page, 'offset': offset})

    posts = []
    for row in result:
        post = {
            'id': row.id,
            'body': row.body,
            'timestamp': row.timestamp,
            'user_id': row.user_id,
            'author': {
                'username': row.username,
                'avatar': User(email=row.email).avatar(70)  # 調用 User 模型的 avatar 方法生成頭像URL
            }
        }
        posts.append(post)

    sql_count = text("""
        SELECT COUNT(*) FROM post
    """)
    total_posts = db.session.execute(sql_count).scalar()

    has_next = page * per_page < total_posts
    has_prev = page > 1
    next_url = url_for('explore', page=page+1) if has_next else None
    prev_url = url_for('explore', page=page-1) if has_prev else None

    return render_template('index.html', title='探索', posts=posts,
                           next_url=next_url, prev_url=prev_url)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
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
            return redirect(url_for('register'))

        if password != password2:
            flash('密碼不一致')
            return redirect(url_for('register'))

        # 創建新使用者
        hashed_password = generate_password_hash(password)
        sql = text('INSERT INTO user (username, email, password_hash) VALUES (:username, :email, :password_hash)')
        db.session.execute(sql, {'username': username, 'email': email, 'password_hash': hashed_password})  
        db.session.commit()

        flash('註冊成功')    
        return redirect(url_for('login'))

    return render_template('register.html', title='Register', csrf_token=generate_csrf())

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
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
                return redirect(url_for('index'))
            else:
                flash('密碼錯誤')
                return redirect(url_for('login'))
        else:
            flash('使用者名稱不存在')
            return redirect(url_for('login'))

    return render_template('login.html', title='Log in', csrf_token=generate_csrf)
        
@app.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.email == form.email.data))
        if user:
            send_password_reset_email(user)
        flash('請檢查你的電子郵件以獲取重設密碼的指示')
        return redirect(url_for('login'))
    return render_template('reset_password_request.html',
                           title='重設密碼', form=form)

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('index'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been reset.')
        return redirect(url_for('login'))
    return render_template('reset_password.html', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/user/<username>')
@login_required
def user(username):
    sql_user = text("SELECT * FROM user WHERE username = :username")
    user = db.session.execute(sql_user, {'username': username}).fetchone()
    
    if user is None:
        return render_template('404.html'), 404
    
    page = request.args.get('page', 1, type=int)
    per_page = app.config['POSTS_PER_PAGE']
    offset = (page - 1) * per_page
    
    sql = text("""
        SELECT * FROM post 
        JOIN user ON post.user_id = user.id
        WHERE post.user_id = :user_id
        ORDER BY timestamp DESC
        LIMIT :per_page OFFSET :offset
    """)
    result = db.session.execute(sql, {'user_id': user.id, 'per_page': per_page, 'offset': offset})
    
    posts = []
    for row in result:
        post = {
            'id': row.id,
            'body': row.body,
            'timestamp': row.timestamp,
            'user_id': row.user_id,
            'author': {
                'username': row.username,
                'avatar': User(email=row.email).avatar(70) 
            }
        }
        posts.append(post)


    sql_count = text("""
        SELECT COUNT(*) FROM post 
        WHERE user_id = :user_id
    """)
    total_posts = db.session.execute(sql_count, {'user_id': user.id}).scalar()
    
    has_next = page * per_page < total_posts
    has_prev = page > 1
    next_url = url_for('user', username=username, page=page+1) if has_next else None
    prev_url = url_for('user', username=username, page=page-1) if has_prev else None
    
    form = EmptyForm()
    return render_template('user.html', user=user, posts=posts,
                           next_url=next_url, prev_url=prev_url, form=form)


@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.now(timezone.utc)
        db.session.commit()

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', title='Edit Profile',form=form)

@app.route('/follow/<username>', methods=['POST'])
@login_required
def follow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == username))
        if user is None:
            flash(f'User {username} not found.')
            return redirect(url_for('index'))
        if user == current_user:
            flash('You cannot follow yourself!')
            return redirect(url_for('user', username=username))
        current_user.follow(user)
        db.session.commit()
        flash(f'You are following {username}!')
        return redirect(url_for('user', username=username))
    else:
        return redirect(url_for('index'))


@app.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == username))
        if user is None:
            flash(f'User {username} not found.')
            return redirect(url_for('index'))
        if user == current_user:
            flash('You cannot unfollow yourself!')
            return redirect(url_for('user', username=username))
        current_user.unfollow(user)
        db.session.commit()
        flash(f'You are not following {username}.')
        return redirect(url_for('user', username=username))
    else:
        return redirect(url_for('index'))
    