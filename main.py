import os

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
from flask import Flask
import requests
from flask import request, jsonify, render_template, redirect, url_for, flash, session
import numpy as np
import json
import base64
import io
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, func, desc
from datetime import datetime, date
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


# # new at 0223 12:46
# from tensorflow.python.platform import build_info
# print(build_info.cuda_version_number)
DIFY_API_URL = 'https://api.dify.ai/v1/workflows/run'

# 在文件开头添加全局变量字典，用于存储每个用户的会话ID
user_conversations = {}

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
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    gender = db.Column(db.String(10))
    birth_date = db.Column(db.Date)  # 将 age 改为 birth_date
    participant_id = db.Column(db.String(10), default='0000')  # 添加新字段
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
    

def calculate_age(birth_date):
    today = date.today()
    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    return age


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        gender = request.form.get('gender')
        birth_date = request.form.get('birth_date')
        participant_id = request.form.get('participant_id', '0000')  # 获取新字段，默认值为'0000'
        
        try:
            birth_date = datetime.strptime(birth_date, '%Y-%m-%d').date()
            # 验证年龄是否在合理范围内（例如：0-120岁）
            today = date.today()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
            if age < 0 or age > 120:
                flash('Please enter a valid birth date', 'warning')
                return redirect(url_for('signup'))
        except ValueError:
            flash('Please enter a valid birth date', 'warning')
            return redirect(url_for('signup'))
        
        # 验证性别是否为有效选项
        if gender not in ['male', 'female', 'other']:
            flash('Please select a valid gender', 'warning')
            return redirect(url_for('signup'))
        
        user = User.query.filter_by(username=username).first()
        if user:
            flash('username already exists', 'warning')
            return redirect(url_for('signup'))
        
        new_user = User(
            username=username, 
            email=email,
            gender=gender,
            birth_date=birth_date,
            participant_id=participant_id  # 添加新字段
        )
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
    # 清除用户的会话ID
    user_id = str(current_user.id)
    if user_id in user_conversations:
        del user_conversations[user_id]
    
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
    writing_mode = db.Column(db.String(50), nullable=False)  # 'manual', 'dialogue', 'feedback'
    story_status = db.Column(db.String(50), default='Visible to Researchers')  # 添加新字段

    def __repr__(self):
        return f'<Story {self.title}>'
    
    def to_dict(self):
        return {
            "id": self.id,
            "time": self.time.isoformat(),  # 将日期时间对象转换为字符串
            "title":self.title,
            "content": self.content,
            "user_id": self.user_id,
            "writing_mode": self.writing_mode,
            "story_status": self.story_status
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
# @app.route('/load_profile', methods=['GET'])
# @login_required
# def load_profile():
#     user = User.query.get(current_user.id)

#     if user:
#         # 获取用户的所有故事并转换为字典格式
#         stories = Story.query.filter_by(user_id=user.id).all()
#         stories_data = [{
#             "id": story.id,
#             "title": story.title,
#             "content": story.content,
#             "time": story.time.isoformat() if story.time else None
#         } for story in stories]
        
#         profile_data = {
#             "username": user.username,
#             "gender": user.gender,
#             "age": user.age,
#             "stories": stories_data
#         }
#         return jsonify(profile_data)
#     return jsonify({"error": "User not found"}), 404
@app.route('/load_profile', methods=['GET'])
@login_required
def load_profile():
    user = User.query.get(current_user.id)
    if user:
        profile_data = {
            "username": user.username,
            "gender": user.gender,
            "birth_date": user.birth_date.strftime('%Y-%m-%d') if user.birth_date else None
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
        user.gender = data.get('gender')
        birth_date = data.get('birth_date')
        if birth_date:
            user.birth_date = datetime.strptime(birth_date, '%Y-%m-%d').date()
        
        db.session.commit()
        return jsonify({"success": True})

    return jsonify({"error": "User not found"}), 404



@app.route('/freewrite', methods=['GET', 'POST'])
@login_required
def free_write():
    return render_template('freewrite.html', user_id=session.get('user_id'))

@app.route('/save_story', methods=['POST'])
@login_required
def save_story():
    try:
        data = request.get_json()
        title = data.get('title')
        content = data.get('content')
        writing_mode = data.get('writing_mode')
        
        if not all([title, content, writing_mode]):
            return jsonify({'error': 'Title, content and writing mode cannot be empty'}), 400
        
        # 验证写作模式是否有效
        valid_modes = ['manual', 'dialogue', 'feedback', 'daily_log']  # 添加 'daily_log'
        if writing_mode not in valid_modes:
            return jsonify({'error': 'Invalid writing mode'}), 400
        
        new_story = Story(
            title=title,
            content=content,
            user_id=current_user.id,
            writing_mode=writing_mode
        )
        
        db.session.add(new_story)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Story saved successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# chatbot1
@app.route('/storygenerate')
@login_required
def story_generate():
    user = User.query.get(current_user.id)
    age = calculate_age(user.birth_date) if user.birth_date else None
    return render_template('storygenerate.html', username=user.username, gender=user.gender, age=age)

#获取参数
# def get_dify_parameters():
#     parameters_url = "https://api.dify.ai/v1/parameters"
    
#     headers = {
#         "Authorization": "Bearer xxxxxxxx"
#     }
    
#     try:
#         response = requests.get(parameters_url, headers=headers)
#         response.raise_for_status()  # 如果请求失败会抛出异常
#         return response.json()
#     except Exception as e:
#         app.logger.error(f"Error getting parameters: {str(e)}")
#         return None







#dify聊天调用
###################################################################################
def dify_chatbot_request(prompt):
    dify_api_url = "https://api.dify.ai/v1/chat-messages"
    
    headers = {
        "Authorization": "Bearer xxxxxxxx",
        "Content-Type": "application/json"
    }
    user = User.query.get(current_user.id)
    
    # 获取当前用户的 conversation_id
    current_conversation_id = user_conversations.get(str(user.id), "")

    #打印参数
    # parameters = get_dify_parameters()
    # if parameters:
    #     print("Dify Parameters:", parameters)


    data = {
        "inputs": {"username": user.username, "gender": str(user.gender), "age": str(calculate_age(user.birth_date))},
        "query": prompt,
        "response_mode": "blocking",
        "conversation_id": current_conversation_id,
        "user": str(user.id)
    }
    
    response = requests.post(dify_api_url, headers=headers, data=json.dumps(data))
    response_json = response.json()
    print(response_json)
    
    # 如果是新对话，保存 conversation_id
    if not current_conversation_id and 'conversation_id' in response_json:
        user_conversations[str(user.id)] = response_json['conversation_id']
    
    return response_json

# 添加聊天路由
@app.route('/chat', methods=['POST'])
@login_required
def chat():
    try:
        message = request.json.get('message')
        if not message:
            return jsonify({'error': 'Message is required'}), 400

        # 调用 Dify API
        dify_response = dify_chatbot_request(message)
        response_text = dify_response.get('answer', 'sorry, I cannot answer this question now.')
        #输出
        print("Chat Response:", dify_response)# 构建回复
        
        response = {
            "fulfillment_response": {
                "messages": [{"text": {"text": [response_text]}}]
            }
        }

        return jsonify(response)

    except Exception as e:
        app.logger.error(f"Chat error: {str(e)}")
        return jsonify({
            "fulfillment_response": {
                "messages": [{"text": {"text": ["sorry, something went wrong"]}}]
            }
        }), 500

# 添加清除会话的路由
@app.route('/clear_chat', methods=['POST'])
@login_required
def clear_chat():
    try:
        user_id = str(current_user.id)
        if user_id in user_conversations:
            del user_conversations[user_id]
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# #chatbot2
###################################################################################
@app.route('/storywrite', methods=['GET', 'POST'])
@login_required
def story_write():
    if request.method == 'POST':
        try:
            story = request.json.get('story')  # 从前端获取用户输入
            if not story:
                return jsonify({'error': 'Story content is required'}), 400

            # 打印故事长度以进行调试
            app.logger.info(f"Story length: {len(story)}")

            # 调用 Dify API 获取反馈
            headers = {
                "Authorization": "Bearer xxxxxxxx",
                "Content-Type": "application/json"
            }
            
            # 如果故事太长，可以截取一部分
            max_length = 2000  # 设置最大长度
            if len(story) > max_length:
                story = story[:max_length] + "..."
            
            data = {
                "inputs": {"stories": story},
                "response_mode": "blocking",
                "user": str(current_user.id)  # 使用当前用户ID
            }

            app.logger.info("Sending request to Dify API")
            response = requests.post(
                DIFY_API_URL, 
                headers=headers, 
                data=json.dumps(data),
                timeout=30  # 增加超时时间
            )
            
            app.logger.info(f"Dify API response status: {response.status_code}")
            
            if response.status_code != 200:
                error_message = f"Dify API error: {response.text}"
                app.logger.error(error_message)
                return jsonify({'error': error_message}), response.status_code

            result = response.json()
            feedback_text = result.get("data", {}).get("outputs", {}).get("output", "No output available.")
            score = result.get("data", {}).get("outputs", {}).get("score", "No score available.")
            
            return jsonify({
                'feedback': feedback_text,
                'score': score
            })

        except requests.Timeout:
            error_message = "Request timed out. Please try with a shorter story."
            app.logger.error(error_message)
            return jsonify({'error': error_message}), 504
            
        except Exception as e:
            error_message = f"Error processing request: {str(e)}"
            app.logger.error(error_message)
            return jsonify({'error': error_message}), 500

    return render_template('storywrite.html', user_id=session.get('user_id'))

# 添加新的路由
@app.route('/my_stories')
@login_required
def my_stories():
    return render_template('my_stories.html')

@app.route('/get_stories')
@login_required
def get_stories():
    stories = Story.query.filter_by(user_id=current_user.id).order_by(desc(Story.time)).all()
    return jsonify({
        'stories': [story.to_dict() for story in stories]
    })

@app.route('/story/<int:story_id>')
@login_required
def story_detail(story_id):
    story = Story.query.get_or_404(story_id)
    # if story.user_id != current_user.id:
    #     abort(403)
    return render_template('story_detail.html')

@app.route('/get_story/<int:story_id>')
@login_required
def get_story(story_id):
    story = Story.query.get_or_404(story_id)
    # if story.user_id != current_user.id:
    #     abort(403)
    return jsonify(story.to_dict())

@app.route('/update_story/<int:story_id>', methods=['POST'])
@login_required
def update_story(story_id):
    story = Story.query.get_or_404(story_id)
    
    data = request.get_json()
    story.content = data.get('content', story.content)
    story.story_status = data.get('story_status', story.story_status)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/delete_story/<int:story_id>', methods=['DELETE'])
@login_required
def delete_story(story_id):
    story = Story.query.get_or_404(story_id)
    # if story.user_id != current_user.id:
    #     abort(403)
    
    db.session.delete(story)
    db.session.commit()
    return jsonify({'success': True})

def update_existing_users():
    with app.app_context():
        # 首先添加新列
        try:
            db.session.execute(text('ALTER TABLE user ADD COLUMN participant_id VARCHAR(10) DEFAULT "0000"'))
            db.session.commit()
        except Exception as e:
            print(f"Column might already exist: {e}")
            db.session.rollback()
        
        # 更新所有现有用户的 participant_id
        try:
            db.session.execute(text('UPDATE user SET participant_id = "0000" WHERE participant_id IS NULL'))
            db.session.commit()
        except Exception as e:
            print(f"Error updating existing users: {e}")
            db.session.rollback()

# 添加数据库迁移函数
def update_existing_stories():
    with app.app_context():
        try:
            db.session.execute(text('ALTER TABLE story ADD COLUMN story_status VARCHAR(50) DEFAULT "Visible to Researchers"'))
            db.session.commit()
        except Exception as e:
            print(f"Column might already exist: {e}")
            db.session.rollback()
        
        try:
            db.session.execute(text('UPDATE story SET story_status = "Visible to Researchers" WHERE story_status IS NULL'))
            db.session.commit()
        except Exception as e:
            print(f"Error updating existing stories: {e}")
            db.session.rollback()

@app.route('/inspiration')
@login_required
def inspiration():
    return render_template('inspiration.html')

def daily_log_chatbot_request(prompt):
    dify_api_url = "https://api.dify.ai/v1/chat-messages"
    
    headers = {
        "Authorization": "Bearer xxxxxxxxxxxxxxxxx",  # 使用新的 API key
        "Content-Type": "application/json"
    }
    user = User.query.get(current_user.id)
    
    # 获取当前用户的 conversation_id
    current_conversation_id = user_conversations.get(f"daily_log_{user.id}", "")

    data = {
        "inputs": {
            "username": user.username,
            "gender": str(user.gender),
            "age": str(calculate_age(user.birth_date))
        },
        "query": prompt,
        "response_mode": "blocking",
        "conversation_id": current_conversation_id,
        "user": str(user.id)
    }
    
    response = requests.post(dify_api_url, headers=headers, data=json.dumps(data))
    response_json = response.json()
    
    # 如果是新对话，保存 conversation_id
    if not current_conversation_id and 'conversation_id' in response_json:
        user_conversations[f"daily_log_{user.id}"] = response_json['conversation_id']
    
    return response_json

@app.route('/daily_log')
@login_required
def daily_log():
    user = User.query.get(current_user.id)
    age = calculate_age(user.birth_date) if user.birth_date else None
    return render_template('daily_log.html', username=user.username, gender=user.gender, age=age)

@app.route('/daily_log_chat', methods=['POST'])
@login_required
def daily_log_chat():
    try:
        message = request.json.get('message')
        if not message:
            return jsonify({'error': 'Message is required'}), 400

        # 调用 Dify API
        dify_response = daily_log_chatbot_request(message)
        response_text = dify_response.get('answer', 'Sorry, I cannot answer this question now.')
        
        response = {
            "fulfillment_response": {
                "messages": [{"text": {"text": [response_text]}}]
            }
        }

        return jsonify(response)

    except Exception as e:
        app.logger.error(f"Daily log chat error: {str(e)}")
        return jsonify({
            "fulfillment_response": {
                "messages": [{"text": {"text": ["Sorry, something went wrong"]}}]
            }
        }), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        update_existing_users()
        update_existing_stories()
    app.run(port=5000, debug=True)
else:
    application = app