from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, Email, EqualTo

class LoginForm(FlaskForm):
    """用户登录表单"""
    email = StringField('电子邮箱', validators=[
        DataRequired(message="请输入邮箱地址"),
        Email(message="邮箱格式不正确")
    ])
    password = PasswordField('访问密钥', validators=[
        DataRequired(message="请输入密码")
    ])
    remember_me = BooleanField('保持连接状态')
    submit = SubmitField('建立连接')

class RegisterForm(FlaskForm):
    """用户注册表单"""
    username = StringField('代号/用户名', validators=[
        DataRequired(), Length(min=2, max=20)
    ])
    email = StringField('电子邮箱', validators=[
        DataRequired(), Email()
    ])
    password = PasswordField('设置密钥', validators=[
        DataRequired(), Length(min=6, message="密码长度至少6位")
    ])
    confirm_password = PasswordField('确认密钥', validators=[
        DataRequired(), EqualTo('password', message='两次输入的密码不一致')
    ])
    captcha = StringField('验证码', validators=[
        DataRequired(message="请输入验证码"),
        Length(min=4, max=4, message="验证码为4位字符")
    ])
    submit = SubmitField('注册身份')