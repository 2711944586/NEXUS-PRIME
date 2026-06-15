"""
DeepSeek AI 助手服务
提供智能对话、数据分析、代码生成等功能
使用 httpx 直接调用 API，无需 OpenAI SDK
"""
import re
from flask import current_app
from typing import Optional, Dict, List, Tuple
import json
import httpx
from datetime import datetime

try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False

from app.extensions import db
from app.models.auth import User


class AIService:
    """DeepSeek AI 服务封装 - 使用 httpx 直接调用 API"""
    
    # DeepSeek 定价 (每百万 tokens，单位：美元)
    PRICING = {
        'deepseek-chat': {'input': 0.14, 'output': 0.28},
        'deepseek-coder': {'input': 0.14, 'output': 0.28},
    }
    
    def __init__(self):
        self._http_clients = {}  # 缓存 httpx 客户端
        self._tokenizer = None   # 缓存 tokenizer
        self.model = "deepseek-chat"
        self.timeout = 60.0
    
    def _get_tokenizer(self):
        """获取或创建 tokenizer（使用 cl100k_base，与 DeepSeek 兼容）"""
        if not HAS_TIKTOKEN:
            return None
        if self._tokenizer is None:
            try:
                self._tokenizer = tiktoken.get_encoding("cl100k_base")
            except Exception:
                # 如果无法加载，返回 None，后续使用估算方法
                return None
        return self._tokenizer
    
    def count_tokens(self, text: str, method: str = 'auto') -> Dict:
        """
        计算文本的 token 数量
        
        Args:
            text: 要计算的文本
            method: 计算方法 ('tiktoken', 'estimate', 'auto')
            
        Returns:
            {
                'tokens': int,           # token 数量
                'characters': int,       # 字符数
                'words': int,            # 单词数（中文按字计算）
                'method': str,           # 使用的计算方法
                'cost_estimate': {       # 费用估算
                    'input': float,      # 作为输入的费用（美元）
                    'output': float      # 作为输出的费用（美元）
                }
            }
        """
        if not text:
            return {
                'tokens': 0,
                'characters': 0,
                'words': 0,
                'method': 'empty',
                'cost_estimate': {'input': 0, 'output': 0}
            }
        
        characters = len(text)
        # 计算单词数：英文按空格分，中文按字计算
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        words = chinese_chars + english_words
        
        tokens = 0
        used_method = 'estimate'
        
        if method in ('tiktoken', 'auto'):
            tokenizer = self._get_tokenizer()
            if tokenizer:
                try:
                    tokens = len(tokenizer.encode(text))
                    used_method = 'tiktoken'
                except Exception:
                    pass
        
        if used_method == 'estimate' or method == 'estimate':
            # 估算方法：中文约 1.5 token/字，英文约 0.75 token/词
            tokens = int(chinese_chars * 1.5 + english_words * 0.75 + len(re.findall(r'[^\w\s]', text)) * 0.5)
            tokens = max(tokens, 1)
            used_method = 'estimate'
        
        # 计算费用估算
        pricing = self.PRICING.get(self.model, self.PRICING['deepseek-chat'])
        cost_input = (tokens / 1_000_000) * pricing['input']
        cost_output = (tokens / 1_000_000) * pricing['output']
        
        return {
            'tokens': tokens,
            'characters': characters,
            'words': words,
            'method': used_method,
            'cost_estimate': {
                'input': round(cost_input, 6),
                'output': round(cost_output, 6)
            }
        }
    
    def estimate_conversation_cost(self, messages: List[Dict]) -> Dict:
        """
        估算整个对话的 token 使用和费用
        
        Args:
            messages: 对话历史 [{'role': 'user', 'content': '...'}, ...]
            
        Returns:
            {
                'total_tokens': int,
                'input_tokens': int,
                'output_tokens': int,
                'estimated_cost': float,
                'breakdown': [...]
            }
        """
        input_tokens = 0
        output_tokens = 0
        breakdown = []
        
        for msg in messages:
            content = msg.get('content', '')
            role = msg.get('role', 'user')
            result = self.count_tokens(content)
            
            if role in ('user', 'system'):
                input_tokens += result['tokens']
            else:
                output_tokens += result['tokens']
            
            breakdown.append({
                'role': role,
                'tokens': result['tokens'],
                'preview': content[:50] + '...' if len(content) > 50 else content
            })
        
        pricing = self.PRICING.get(self.model, self.PRICING['deepseek-chat'])
        cost = (input_tokens / 1_000_000) * pricing['input'] + (output_tokens / 1_000_000) * pricing['output']
        
        return {
            'total_tokens': input_tokens + output_tokens,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'estimated_cost': round(cost, 6),
            'breakdown': breakdown
        }
    
    def _get_credentials(self, api_key: Optional[str] = None, base_url: Optional[str] = None) -> Tuple[Optional[str], str]:
        """获取 API 凭证"""
        default_key = current_app.config.get('DEEPSEEK_API_KEY', '')
        default_base = current_app.config.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
        
        key = api_key or default_key
        endpoint = base_url or default_base
        
        # 验证 API Key
        if not key or key == 'sk-placeholder' or len(key) < 10:
            return None, endpoint
        
        return key, endpoint
    
    def _get_http_client(self) -> httpx.Client:
        """获取或创建 httpx 客户端"""
        if 'default' not in self._http_clients:
            self._http_clients['default'] = httpx.Client(timeout=self.timeout)
        return self._http_clients['default']
    
    def is_configured(self, user: Optional[User] = None) -> bool:
        """检查 AI 服务是否已正确配置"""
        user_key, _ = self._resolve_user_credentials(user)
        if user_key and len(user_key) >= 10:
            return True
        
        default_key = current_app.config.get('DEEPSEEK_API_KEY', '')
        return bool(default_key and default_key != 'sk-placeholder' and len(default_key) >= 10)
    
    @staticmethod
    def _resolve_user_credentials(user: Optional[User]) -> Tuple[Optional[str], Optional[str]]:
        """从用户偏好中提取 AI 密钥/自定义地址"""
        if not user:
            return None, None
        prefs = user.preferences or {}
        if not isinstance(prefs, dict):
            return None, None
        return prefs.get('ai_api_key'), prefs.get('ai_api_base')
    
    def chat(
        self, 
        message: str, 
        user: Optional[User] = None,
        context: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None
    ) -> Dict:
        """
        发送消息到 DeepSeek AI（使用 httpx 直接调用）
        
        Args:
            message: 用户消息
            user: 用户对象（用于获取个人API Key）
            context: 对话上下文历史 [{"role": "user", "content": "..."}, ...]
            system_prompt: 系统提示词（可选）
            
        Returns:
            {"success": bool, "content": str, "usage": dict, "error": str}
        """
        try:
            # 获取用户凭证
            user_api_key, user_base = self._resolve_user_credentials(user)
            
            # 获取 API 凭证
            api_key, base_url = self._get_credentials(api_key=user_api_key, base_url=user_base)

            # 如果没有外部 API Key，且开启了本地回退模式，则使用本地策略生成回应
            if not api_key:
                if current_app.config.get('AI_FALLBACK', False):
                    try:
                        # 简单语义判断：如果请求与库存相关，则调用库存分析模块
                        text_context = message + ' ' + ' '.join([c.get('content', '') for c in (context or [])])
                        if '库存' in text_context or '盘点' in text_context or '补货' in text_context:
                            content = self.analyze_inventory(user=user)
                        else:
                            # 基础本地回退答复（可以扩展为规则引擎或本地模型）
                            content = (
                                "（本地回退）已收到您的请求，但系统未配置外部 AI。"
                                f" 我已对问题进行简单分析：\n\n{message[:100]}\n\n"
                                "提示：如需更智能的回复，请在 系统设置 -> AI 设置 中配置 DeepSeek API Key。"
                            )

                        return {
                            "success": True,
                            "content": content,
                            "usage": {},
                            "error": None
                        }
                    except Exception as e:
                        return {
                            "success": False,
                            "content": "",
                            "usage": {},
                            "error": f"本地回退失败: {str(e)}"
                        }

                return {
                    "success": False,
                    "content": "",
                    "usage": {},
                    "error": "AI 服务未配置。请在用户设置中配置您的 DeepSeek API Key，或联系管理员配置系统级 API Key。"
                }
            
            # 构建消息列表
            messages = []
            
            # 添加系统提示
            if not system_prompt:
                system_prompt = """你是 NEXUS PRIME 企业管理系统的智能助手。
你的职责是帮助用户：
1. 解答系统使用问题
2. 分析业务数据并提供洞察
3. 生成报表和可视化建议
4. 优化库存和销售策略
5. 提供 Python/Flask 代码帮助

请用专业、友好的语气回答，必要时使用 Markdown 格式。"""
            
            messages.append({"role": "system", "content": system_prompt})
            
            # 添加历史上下文（最多保留最近 10 条）
            if context:
                messages.extend(context[-10:])
            
            # 添加当前消息
            messages.append({"role": "user", "content": message})
            
            # 使用 httpx 直接调用 DeepSeek API
            client = self._get_http_client()
            
            # 确保 base_url 以 /v1 结尾
            api_url = base_url.rstrip('/')
            if not api_url.endswith('/v1'):
                api_url += '/v1'
            
            response = client.post(
                f"{api_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 2000,
                    "stream": False
                }
            )
            
            # 检查响应状态
            if response.status_code != 200:
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = error_json.get('error', {}).get('message', error_detail)
                except:
                    pass
                raise Exception(f"API 返回错误 ({response.status_code}): {error_detail}")
            
            # 解析响应
            result = response.json()
            assistant_message = result['choices'][0]['message']['content']
            usage = result.get('usage', {})
            
            # 记录到数据库（如果配置了 AiChatLog 模型）
            self._save_chat_log(getattr(user, 'id', None), message, assistant_message, usage)
            
            return {
                "success": True,
                "content": assistant_message,
                "usage": {
                    "prompt_tokens": usage.get('prompt_tokens', 0),
                    "completion_tokens": usage.get('completion_tokens', 0),
                    "total_tokens": usage.get('total_tokens', 0)
                },
                "error": None
            }
            
        except httpx.TimeoutException:
            return {
                "success": False,
                "content": "",
                "usage": {},
                "error": "AI 服务响应超时，请稍后重试。"
            }
        except httpx.ConnectError:
            return {
                "success": False,
                "content": "",
                "usage": {},
                "error": "无法连接到 AI 服务，请检查网络连接。"
            }
        except Exception as e:
            error_msg = str(e)
            current_app.logger.error(f"DeepSeek API Error: {error_msg}")
            
            # 提供更友好的错误信息
            if 'api_key' in error_msg.lower() or 'authentication' in error_msg.lower() or '401' in error_msg:
                friendly_error = "API Key 无效或已过期，请检查您的 DeepSeek API Key 配置。"
            elif 'timeout' in error_msg.lower():
                friendly_error = "AI 服务响应超时，请稍后重试。"
            elif 'connection' in error_msg.lower():
                friendly_error = "无法连接到 AI 服务，请检查网络连接。"
            else:
                friendly_error = f"AI 服务暂时不可用: {error_msg}"
            
            return {
                "success": False,
                "content": "",
                "usage": {},
                "error": friendly_error
            }
    
    def _save_chat_log(self, user_id: Optional[int], user_msg: str, ai_msg: str, usage: dict):
        """保存对话记录到数据库"""
        try:
            # 尝试导入 AiChatLog 模型（如果存在）
            from app.models.sys import AiChatLog
            
            log = AiChatLog(
                user_id=user_id,
                prompt=user_msg,
                response=ai_msg,
                model_version=self.model
            )
            db.session.add(log)
            db.session.commit()
        except ImportError:
            # AiChatLog 模型不存在，跳过保存
            pass
        except Exception as e:
            current_app.logger.warning(f"Failed to save chat log: {str(e)}")
            db.session.rollback()
    
    def analyze_inventory(self, limit: int = 10, user: Optional[User] = None) -> str:
        """分析库存数据并生成建议"""
        try:
            from sqlalchemy import func
            from app.models.biz import Product
            from app.models.stock import Stock
            
            qty_expr = func.coalesce(func.sum(Stock.quantity), 0)
            stock_query = (
                db.session.query(
                    Product,
                    qty_expr.label('qty')
                )
                .outerjoin(Stock, Stock.product_id == Product.id)
                .group_by(Product.id)
            )
            
            low_stock = stock_query.order_by(qty_expr.asc()).limit(limit).all()
            high_stock = stock_query.order_by(qty_expr.desc()).limit(limit).all()
            
            def serialize(items):
                return [
                    {
                        "sku": product.sku,
                        "name": product.name,
                        "quantity": int(qty),
                        "price": float(product.price) if product.price else 0
                    }
                    for product, qty in items
                ]
            
            analysis = {
                "low_stock_count": len(low_stock),
                "high_stock_count": len(high_stock),
                "low_stock_items": serialize(low_stock),
                "high_stock_items": serialize(high_stock)
            }
            
            # 让 AI 生成分析报告
            prompt = f"""请分析以下库存数据并提供优化建议：

低库存产品（{analysis['low_stock_count']} 个）：
{json.dumps(analysis['low_stock_items'], ensure_ascii=False, indent=2)}

高库存产品（{analysis['high_stock_count']} 个）：
{json.dumps(analysis['high_stock_items'], ensure_ascii=False, indent=2)}

请提供：
1. 风险评估
2. 补货建议
3. 促销建议
4. 库存优化策略"""
            
            result = self.chat(prompt, system_prompt="你是一位专业的供应链管理顾问。", user=user)
            return result.get('content', '分析失败')
            
        except Exception as e:
            return f"库存分析失败: {str(e)}"
    
    def generate_report(self, report_type: str, data: Dict, user: Optional[User] = None) -> str:
        """生成各类报表分析"""
        prompts = {
            "sales": "分析销售数据并生成销售报表",
            "inventory": "生成库存周转率分析报告",
            "customer": "分析客户购买行为和偏好",
            "financial": "生成财务概览和趋势分析"
        }
        
        prompt = f"""{prompts.get(report_type, '生成数据分析报告')}

数据：
{json.dumps(data, ensure_ascii=False, indent=2)}

请提供详细的分析报告，包括关键指标、趋势、异常点和优化建议。"""
        
        result = self.chat(prompt, system_prompt="你是一位资深的商业数据分析师。", user=user)
        return result.get('content', '报告生成失败')


# 全局单例
ai_service = AIService()
