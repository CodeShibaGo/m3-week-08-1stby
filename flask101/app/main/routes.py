from datetime import datetime, timezone
from flask import render_template, flash, redirect, url_for, request, session, current_app
from flask_login import current_user, login_required
import sqlalchemy as sa
from langdetect import detect, LangDetectException
from app import db
from app.main.forms import EditProfileForm, EmptyForm, PostForm
from app.models import User, Post
from app.main import bp
from sqlalchemy import text


@bp.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.now(timezone.utc)
        db.session.commit()

@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    form = PostForm()
    if form.validate_on_submit():
        try:
            language = detect(form.post.data)
        except LangDetectException:
            language = ''
        post_body = form.post.data
        user_id = current_user.id
        timestamp = datetime.now(timezone.utc)
        sql = text("INSERT INTO post (body, user_id, timestamp, language)  VALUES (:body, :user_id, :timestamp, :language)")
        db.session.execute(sql, {'body': post_body, 'user_id': user_id, 'timestamp':timestamp, 'language':language})
        db.session.commit()
        flash('你的貼文現在已發布！')
        return redirect(url_for('main.index'))
    
    page = request.args.get('page', 1, type=int)
    per_page =current_app.config['POSTS_PER_PAGE']
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
    next_url = url_for('main.index', page=page+1) if has_next else None
    prev_url = url_for('main.index', page=page-1) if has_prev else None

    return render_template('index.html', title='首頁', form=form,
                           posts=posts, next_url=next_url, prev_url=prev_url)

@bp.route('/explore')
@login_required
def explore():
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config['POSTS_PER_PAGE']
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
    next_url = url_for('main.explore', page=page+1) if has_next else None
    prev_url = url_for('main.explore', page=page-1) if has_prev else None

    return render_template('index.html', title='探索', posts=posts,
                           next_url=next_url, prev_url=prev_url)


@bp.route('/user/<username>')
@login_required
def user(username):
    sql_user = text("SELECT * FROM user WHERE username = :username")
    user = db.session.execute(sql_user, {'username': username}).fetchone()
    
    if user is None:
        return render_template('404.html'), 404
    
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config['POSTS_PER_PAGE']
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
    next_url = url_for('main.user', username=username, page=page+1) if has_next else None
    prev_url = url_for('main.user', username=username, page=page-1) if has_prev else None
    
    form = EmptyForm()
    return render_template('user.html', user=user, posts=posts,
                           next_url=next_url, prev_url=prev_url, form=form)

@bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('main.edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', title='Edit Profile',form=form)

@bp.route('/follow/<username>', methods=['POST'])
@login_required
def follow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == username))
        if user is None:
            flash(f'User {username} not found.')
            return redirect(url_for('main.index'))
        if user == current_user:
            flash('You cannot follow yourself!')
            return redirect(url_for('main.user', username=username))
        current_user.follow(user)
        db.session.commit()
        flash(f'You are following {username}!')
        return redirect(url_for('main.user', username=username))
    else:
        return redirect(url_for('main.index'))
    
@bp.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == username))
        if user is None:
            flash(f'User {username} not found.')
            return redirect(url_for('main.index'))
        if user == current_user:
            flash('You cannot unfollow yourself!')
            return redirect(url_for('main.user', username=username))
        current_user.unfollow(user)
        db.session.commit()
        flash(f'You are not following {username}.')
        return redirect(url_for('main.user', username=username))
    else:
        return redirect(url_for('main.index'))
        
