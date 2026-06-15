"""AI 助手路由"""
from flask import render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime

from . import ai_bp
from app.services.ai_service import ai_service
from app.utils.audit import log_action
from app.extensions import db, csrf
from app.models.sys import AiChatSession, AiChatMessage


@ai_bp.route('/chat', methods=['GET'])
@login_required
def chat_page():
    """AI 对话页面"""
    # 检查是否有真实的API Key（用户配置的或环境变量中的）
    has_real_key = _has_real_api_key()
    # 如果没有真实key但启用了本地回退模式，显示回退模式提示
    show_fallback_mode = not has_real_key and current_app.config.get('AI_FALLBACK', False)
    return render_template('ai/chat.html', has_real_key=has_real_key, show_fallback_mode=show_fallback_mode)


def _has_real_api_key():
    """检查是否有真实可用的 API Key（不含fallback）"""
    prefs = current_user.preferences or {}
    user_key = prefs.get('ai_api_key') if isinstance(prefs, dict) else None
    # 用户配置了有效的key
    if user_key and len(user_key) >= 10:
        return True
    # 环境变量中有有效的key
    env_key = current_app.config.get('DEEPSEEK_API_KEY', '')
    if env_key and not env_key.endswith('placeholder') and not env_key.startswith('sk-placeholder') and len(env_key) >= 10:
        return True
    return False


def _has_available_api_key():
    """确保存在可用的 API Key（包含fallback模式）"""
    if _has_real_api_key():
        return True
    # 若配置了 AI_FALLBACK，则视为可用（系统会使用本地回退）
    return current_app.config.get('AI_FALLBACK', False)


# ==================== 会话管理 API ====================

@ai_bp.route('/api/sessions', methods=['GET'])
@csrf.exempt
@login_required
def get_sessions():
    """获取用户的所有对话会话"""
    try:
        sessions = AiChatSession.query.filter_by(
            user_id=current_user.id,
            is_archived=False
        ).order_by(AiChatSession.last_message_at.desc()).limit(50).all()
        
        return jsonify({
            'success': True,
            'sessions': [s.to_dict() for s in sessions]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@ai_bp.route('/api/sessions', methods=['POST'])
@csrf.exempt
@login_required
def create_session():
    """创建新的对话会话"""
    try:
        data = request.get_json() or {}
        title = data.get('title', '新对话')
        
        session = AiChatSession(
            user_id=current_user.id,
            title=title[:128]
        )
        db.session.add(session)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'session': session.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@ai_bp.route('/api/sessions/<int:session_id>', methods=['GET'])
@csrf.exempt
@login_required
def get_session(session_id):
    """获取会话详情和消息"""
    try:
        session = AiChatSession.query.filter_by(
            id=session_id,
            user_id=current_user.id
        ).first()
        
        if not session:
            return jsonify({'success': False, 'error': '会话不存在'}), 404
        
        messages = [m.to_dict() for m in session.messages.order_by(AiChatMessage.created_at.asc()).all()]
        
        session_dict = session.to_dict()
        session_dict['messages'] = messages
        
        return jsonify({
            'success': True,
            'session': session_dict
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@ai_bp.route('/api/sessions/<int:session_id>', methods=['PUT'])
@csrf.exempt
@login_required
def update_session(session_id):
    """更新会话标题"""
    try:
        session = AiChatSession.query.filter_by(
            id=session_id,
            user_id=current_user.id
        ).first()
        
        if not session:
            return jsonify({'success': False, 'error': '会话不存在'}), 404
        
        data = request.get_json() or {}
        if 'title' in data:
            session.title = data['title'][:128]
        
        db.session.commit()
        return jsonify({'success': True, 'session': session.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@ai_bp.route('/api/sessions/<int:session_id>', methods=['DELETE'])
@csrf.exempt
@login_required
def delete_session(session_id):
    """删除会话"""
    try:
        session = AiChatSession.query.filter_by(
            id=session_id,
            user_id=current_user.id
        ).first()
        
        if not session:
            return jsonify({'success': False, 'error': '会话不存在'}), 404
        
        db.session.delete(session)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 对话 API ====================

@ai_bp.route('/api/chat', methods=['POST'])
@csrf.exempt
@login_required
def api_chat():
    """AI 对话 API - 支持会话持久化"""
    try:
        if not _has_available_api_key():
            return jsonify({
                'success': False,
                'error': '请先在 AI 设置面板中配置可用的 API Key'
            }), 403
        
        data = request.get_json()
        message = data.get('message', '').strip()
        session_id = data.get('sessionId')
        context = data.get('context', [])  # 历史对话
        
        if not message:
            return jsonify({
                'success': False,
                'error': '消息不能为空'
            }), 400
        
        # 获取或创建会话
        session = None
        if session_id:
            session = AiChatSession.query.filter_by(
                id=session_id,
                user_id=current_user.id
            ).first()
        
        if not session:
            # 自动创建新会话，标题取消息前20字
            session = AiChatSession(
                user_id=current_user.id,
                title=message[:20] + ('...' if len(message) > 20 else '')
            )
            db.session.add(session)
            db.session.flush()  # 获取 session.id
        
        # 保存用户消息
        user_msg = AiChatMessage(
            session_id=session.id,
            role='user',
            content=message
        )
        db.session.add(user_msg)
        
        # 如果没有传入 context，从数据库加载历史
        if not context:
            history = session.messages.order_by(AiChatMessage.created_at.asc()).limit(20).all()
            context = [{'role': m.role, 'content': m.content} for m in history]
        
        # 调用 AI 服务
        result = ai_service.chat(
            message=message,
            user=current_user,
            context=context
        )
        
        # 保存 AI 回复
        if result['success']:
            ai_msg = AiChatMessage(
                session_id=session.id,
                role='assistant',
                content=result['content'],
                tokens=result['usage'].get('total_tokens', 0)
            )
            db.session.add(ai_msg)
            
            # 更新会话时间
            session.last_message_at = datetime.utcnow()
            
            # 记录审计日志
            log_action('ai', 'chat', {
                'session_id': session.id,
                'message_preview': message[:50],
                'tokens': result['usage'].get('total_tokens', 0)
            })
        
        db.session.commit()
        
        # 返回结果，包含会话ID
        result['sessionId'] = session.id
        return jsonify(result)
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'服务器错误: {str(e)}'
        }), 500


@ai_bp.route('/api/count-tokens', methods=['POST'])
@csrf.exempt
@login_required
def api_count_tokens():
    """计算文本的 Token 数量"""
    try:
        data = request.get_json()
        text = data.get('text', '')
        method = data.get('method', 'auto')  # 'tiktoken', 'estimate', 'auto'
        
        result = ai_service.count_tokens(text, method)
        return jsonify({
            'success': True,
            **result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'计算失败: {str(e)}'
        }), 500


@ai_bp.route('/api/estimate-cost', methods=['POST'])
@csrf.exempt
@login_required
def api_estimate_cost():
    """估算对话的 Token 使用量和费用"""
    try:
        data = request.get_json()
        messages = data.get('messages', [])
        
        result = ai_service.estimate_conversation_cost(messages)
        return jsonify({
            'success': True,
            **result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'估算失败: {str(e)}'
        }), 500


@ai_bp.route('/api/settings/api-key', methods=['GET', 'POST'])
@csrf.exempt
@login_required
def api_key_settings():
    """管理用户自己的 AI API Key"""
    prefs = current_user.preferences or {}
    if not isinstance(prefs, dict):
        prefs = {}
    
    if request.method == 'GET':
        return jsonify({
            'success': True,
            'hasKey': bool(prefs.get('ai_api_key'))
        })
    
    data = request.get_json() or {}
    api_key = (data.get('apiKey') or '').strip()
    remove = data.get('remove')
    
    if remove:
        prefs.pop('ai_api_key', None)
    else:
        if not api_key:
            return jsonify({'success': False, 'error': 'API Key 不能为空'}), 400
        prefs['ai_api_key'] = api_key
    
    current_user.preferences = prefs
    db.session.commit()
    return jsonify({'success': True})


@ai_bp.route('/api/analyze/inventory', methods=['POST'])
@csrf.exempt
@login_required
def api_analyze_inventory():
    """库存分析 API"""
    try:
        if not _has_available_api_key():
            return jsonify({'success': False, 'error': '请先配置 AI API Key'}), 403
        data = request.get_json()
        limit = data.get('limit', 10)
        
        # 调用库存分析
        analysis = ai_service.analyze_inventory(limit=limit, user=current_user)
        
        log_action('ai', 'inventory_analysis', {'limit': limit})
        
        return jsonify({
            'success': True,
            'content': analysis
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ai_bp.route('/api/report/<report_type>', methods=['POST'])
@csrf.exempt
@login_required
def api_generate_report(report_type):
    """生成报表 API"""
    try:
        if not _has_available_api_key():
            return jsonify({'success': False, 'error': '请先配置 AI API Key'}), 403
        data = request.get_json()
        report_data = data.get('data', {})
        
        # 生成报表
        report = ai_service.generate_report(report_type, report_data, user=current_user)
        
        log_action('ai', 'generate_report', {'type': report_type})
        
        return jsonify({
            'success': True,
            'content': report
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
