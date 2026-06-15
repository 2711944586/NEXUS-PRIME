from datetime import datetime
from app.extensions import db

class BaseModel(db.Model):
    """
    NEXUS 企业级模型基类
    包含：ID主键, 创建时间, 更新时间, 软删除逻辑, 序列化方法
    """
    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 软删除标记：1=已删除, 0=正常
    is_deleted = db.Column(db.Boolean, default=False, index=True)

    def save(self):
        """保存到数据库"""
        db.session.add(self)
        db.session.commit()

    def delete(self, soft=True):
        """删除数据（默认软删除）"""
        if soft:
            self.is_deleted = True
            self.save()
        else:
            db.session.delete(self)
            db.session.commit()

    def to_dict(self):
        """
        通用序列化方法：将模型转换为字典，便于 API 返回 JSON。
        过滤掉以 '_' 开头的私有属性。
        """
        data = {}
        for c in self.__table__.columns:
            if c.name.startswith('_'):
                continue
            val = getattr(self, c.name)
            if isinstance(val, datetime):
                data[c.name] = val.isoformat()
            else:
                data[c.name] = val
        return data