from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Email, Length, Optional

class ProfileForm(FlaskForm):
    """个人信息表单"""
    username = StringField('用户名', validators=[
        DataRequired(message='用户名不能为空'),
        Length(min=2, max=50, message='用户名长度为2-50字符')
    ])
    
    email = StringField('邮箱', validators=[
        DataRequired(message='邮箱不能为空'),
        Email(message='请输入有效的邮箱地址')
    ])
    
    phone = StringField('联系电话', validators=[
        Optional(),
        Length(max=20, message='电话号码过长')
    ])
    
    department = StringField('部门', validators=[
        Optional(),
        Length(max=100, message='部门名称过长')
    ])
    
    position = StringField('职位', validators=[
        Optional(),
        Length(max=100, message='职位名称过长')
    ])
    
    bio = TextAreaField('个人简介', validators=[
        Optional(),
        Length(max=500, message='简介不超过500字符')
    ])
    
    avatar = FileField('头像', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], message='仅支持图片格式')
    ])
    
    theme_preference = SelectField('主题偏好', choices=[
        ('auto', '跟随系统'),
        ('dark', '夜间模式'),
        ('light', '日间模式')
    ])
    
    language = SelectField('语言', choices=[
        ('zh-CN', '简体中文'),
        ('en-US', 'English')
    ])
