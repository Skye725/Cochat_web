import os

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
from flask import Flask
import requests
from flask import request, jsonify, render_template, redirect, url_for, flash, session
import numpy as np
# import cv2
import json
import base64
# from PIL import Image
# from io import BytesIO
# from keras.models import load_model
import io
import os
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, func
from datetime import datetime
from datetime import timedelta
import logging
#from dateutil.parser import parse
from flask_cors import CORS
import sys
from pytz import timezone
#from collections import Counter, defaultdict
import pandas as pd
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
# import tensorflow as tf

# # new at 0223 12:46
# from tensorflow.python.platform import build_info
# print(build_info.cuda_version_number)
DIFY_API_URL = 'https://api.dify.ai/v1/workflows/run'



app = Flask(__name__)
CORS(app)
app.secret_key = 'cs_project_ycy_001'

app.logger.addHandler(logging.StreamHandler(sys.stdout))
app.logger.setLevel(logging.ERROR)

app.logger.setLevel(logging.INFO)
# 添加一个文件处理器
file_handler = logging.FileHandler('app.log')
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)

rootdir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(rootdir, 'db', 'CSProject.db')
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

with app.app_context():
    try:
        # Trying to connect to the database
        db.session.execute(text('SELECT 1'))
        app.logger.info('Successfully connected to the database.')
    except Exception as e:
        # Catch connection exceptions and log them to a log file
        app.logger.error(f'Error connecting to the database: {str(e)}')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

#数据库创建
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # 用户ID（主键）
    username = db.Column(db.String(20), unique=True, nullable=False)  # 用户名
    email = db.Column(db.String(120), unique=True, nullable=False)  # 邮箱
    password = db.Column(db.String(128), nullable=False)  # 密码
    gender = db.Column(db.String(10))  # 性别
    age = db.Column(db.Integer)  # 年龄

    # 定义与 Story 的关系：一个用户可以有多个故事
    stories = db.relationship('Story', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.email}>'

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)
    




@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        user = User.query.filter_by(username=username).first()
        if user:
            flash('username already exists', 'warning')
            return redirect(url_for('signup'))
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash('Signup successfully, please login.', 'success')
        return redirect(url_for('login'))

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            flash('Please check your login details and try again.')
            return redirect(url_for('login'))
        login_user(user, remember=remember)
        session['user_id'] = user.id
        return redirect(url_for('logined_index'))
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    session.pop('user_id', None)
    logout_user()
    return redirect(url_for('login'))


def get_current_time():
    london_t = timezone('Europe/London')
    return datetime.now(london_t)
    # shanghai_t = timezone('Asia/Shanghai')
    # return datetime.now(shanghai_t)




class Story(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # 故事ID（主键）
    time = db.Column(db.DateTime, nullable=False, default=get_current_time)  # 故事时间
    title = db.Column(db.String(200))  # 故事主题
    content = db.Column(db.Text)  # 故事内容
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # 外键，指向 User

    def __repr__(self):
        return f'<Story {self.title}>'
    
    def to_dict(self):
        return {
            "id": self.id,
            "time": self.time.isoformat(),  # 将日期时间对象转换为字符串
            "title":self.title,
            "content": self.content,
            "user_id": self.user_id
        }






@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')

@app.route('/index_login', methods=['GET', 'POST'])
def logined_index():
    return render_template('/index_login.html')


#个人主页
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def pre_img():
    return render_template('profile.html', user_id=session.get('user_id'))

#个人主页信息加载
@app.route('/load_profile', methods=['GET'])
@login_required
def load_profile():
    # Get the current user from the session
    user = User.query.get(current_user.id)

    if user:
        # Retrieve user's profile data and their stories
        stories = Story.query.filter_by(user_id=user.id).all()
        stories_data = [{"id": story.id, "content": story.content} for story in stories]
        
        profile_data = {
            "username": user.username,
            "gender": user.gender,
            "age": user.age,
            "stories": stories_data
        }
        return jsonify(profile_data)
    return jsonify({"error": "User not found"}), 404

#主页信息存储
@app.route('/save_profile', methods=['POST'])
@login_required
def save_profile():
    data = request.get_json()

    user = User.query.get(current_user.id)
    
    if user:
        # Save gender and age
        user.gender = data.get('gender')
        user.age = data.get('age')

        # Save each story
        for story_data in data.get('stories', []):
            story = Story.query.get(story_data['id'])
            if story:
                story.content = story_data['content']
        
        db.session.commit()
        return jsonify({"success": True})

    return jsonify({"error": "User not found"}), 404



# @app.route('/storygenerate', methods=['GET', 'POST'])
# @login_required
# def pre_webcam():
#     return render_template('storygenerate.html', user_id=session.get('user_id'))


# chatbot1
@app.route('/storygenerate')
@login_required
def story_generate():
    # Assuming the user is logged in and their ID is stored in the session
    user = User.query.get(current_user.id)
    return render_template('storygenerate.html', username=user.username, gender=user.gender, age=user.age)




# #chatbot2
# @app.route('/storywrite', methods=['GET', 'POST'])
# @login_required
# def story_write():
#     return render_template('/storywrite.html', user_id=session.get('user_id'))

@app.route('/storywrite', methods=['GET', 'POST'])
@login_required
def story_write():
    if request.method == 'POST':
        story = request.json.get('story')  # 从前端获取用户输入
        if not story:
            return jsonify({'error': 'Story content is required'}), 400

        # 调用 Dify API 获取反馈
        headers = {
            "Authorization": "Bearer XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "Content-Type": "application/json"
        }
        data = {
            "inputs": {"stories": story},
            "response_mode": "blocking",
            "user": session.get('user_id', 'default-user')  # 使用唯一用户ID
        }

        response = requests.post(DIFY_API_URL, headers=headers, data=json.dumps(data))
        
        if response.status_code != 200:
            return jsonify({'error': 'Error fetching feedback'}), response.status_code

        result = response.json()
        feedback_text = result.get("data", {}).get("outputs", {}).get("output", "No output available.")

        return jsonify({'feedback': feedback_text})  # 将反馈结果以 JSON 格式返回

    return render_template('storywrite.html', user_id=session.get('user_id'))










if __name__ == '__main__':
    # print('2')
    with app.app_context():
        print("none")
        db.create_all()
        print('done')
    # print('3')
    app.run(port=5000, debug=True)
else:
    application = app