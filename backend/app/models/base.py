from app.extensions import db
from app.utils.time import utcnow

class BaseModel(db.Model):
    """
    NEXUS 企业级模型基类
    包含：ID主键, 创建时间, 更新时间, 软删除逻辑, 序列化方法
    """
    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_at = db.Column(db.DateTime, default=utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    
    # 软删除标记：1=已删除, 0=正常
    is_deleted = db.Column(db.Boolean, default=False, index=True)

    def save(self):
        """暂存到 session（调用方负责 commit，保证事务原子性）"""
        db.session.add(self)

    def delete(self, soft=True):
        """删除数据（默认软删除）。调用方负责 commit。"""
        if soft:
            self.is_deleted = True
            db.session.add(self)
        else:
            db.session.delete(self)

    _EXCLUDED_COLS = frozenset({'password_hash', 'is_deleted'})

    def to_dict(self):
        """序列化为字典，过滤敏感列。"""
        result = {}
        for c in self.__table__.columns:
            if c.name.startswith('_') or c.name in self._EXCLUDED_COLS:
                continue
            val = getattr(self, c.name)
            if hasattr(val, 'isoformat'):
                result[c.name] = val.isoformat()
            elif hasattr(val, '__float__'):  # Decimal → float for JSON
                result[c.name] = float(val)
            else:
                result[c.name] = val
        return result
