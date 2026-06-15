import json
import re
from time import perf_counter, time
from typing import Any, Dict, List, Optional, Tuple

import httpx
from flask import current_app

try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False

from app.extensions import db
from app.models.auth import User
from app.utils.time import utcnow


class AIService:
    DEFAULT_MODEL = 'deepseek-chat'
    PRICING = {
        'deepseek-chat': {'input': 0.14, 'output': 0.28},
        'deepseek-coder': {'input': 0.14, 'output': 0.28},
    }
    VALID_MODES = {'local', 'hybrid', 'external'}
    PLACEHOLDER_KEY_MARKERS = ('your-', 'change-this', 'example', 'placeholder')
    
    def __init__(self):
        self._http_clients = {}
        self._diagnostic_cache = {}
        self._tokenizer = None
        self.model = self.DEFAULT_MODEL
        self.timeout = 20.0
    
    def _get_tokenizer(self):
        if not HAS_TIKTOKEN:
            return None
        if self._tokenizer is None:
            try:
                self._tokenizer = tiktoken.get_encoding("cl100k_base")
            except Exception:
                return None
        return self._tokenizer
    
    def count_tokens(self, text: str, method: str = 'auto') -> Dict:
        if not text:
            return {
                'tokens': 0,
                'characters': 0,
                'words': 0,
                'method': 'empty',
                'cost_estimate': {'input': 0, 'output': 0}
            }
        
        characters = len(text)
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
            tokens = int(chinese_chars * 1.5 + english_words * 0.75 + len(re.findall(r'[^\w\s]', text)) * 0.5)
            tokens = max(tokens, 1)
            used_method = 'estimate'
        
        pricing = self.PRICING.get(self.model, self.PRICING[self.DEFAULT_MODEL])
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
        
        pricing = self.PRICING.get(self.model, self.PRICING[self.DEFAULT_MODEL])
        cost = (input_tokens / 1_000_000) * pricing['input'] + (output_tokens / 1_000_000) * pricing['output']
        
        return {
            'total_tokens': input_tokens + output_tokens,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'estimated_cost': round(cost, 6),
            'breakdown': breakdown
        }
    
    def _get_credentials(self, api_key: Optional[str] = None, base_url: Optional[str] = None) -> Tuple[Optional[str], str]:
        default_key = current_app.config.get('AI_API_KEY') or ''
        default_base = current_app.config.get('AI_BASE_URL') or 'https://api.deepseek.com'
        
        key = api_key or default_key
        endpoint = base_url or default_base
        
        if not self.is_real_key(key):
            return None, endpoint
        
        return key, endpoint
    
    def _get_http_client(self) -> httpx.Client:
        request_timeout = float(current_app.config.get('AI_REQUEST_TIMEOUT_SECONDS', self.timeout))
        connect_timeout = min(float(current_app.config.get('AI_CONNECT_TIMEOUT_SECONDS', 5.0)), request_timeout)
        key = f'{connect_timeout}:{request_timeout}'
        if key not in self._http_clients:
            self._http_clients[key] = httpx.Client(
                timeout=httpx.Timeout(
                    request_timeout,
                    connect=connect_timeout,
                    read=request_timeout,
                    write=connect_timeout,
                    pool=connect_timeout,
                )
            )
        return self._http_clients[key]

    @staticmethod
    def _preferences(user: Optional[User]) -> Dict[str, Any]:
        if not user or not isinstance(user.preferences, dict):
            return {}
        return user.preferences

    def _resolve_mode(self, user: Optional[User]) -> str:
        mode = self._preferences(user).get('analysis_mode')
        if mode in self.VALID_MODES:
            return mode
        return 'hybrid' if self.is_configured(user) else 'local'

    def _default_model(self) -> str:
        return (current_app.config.get('AI_MODEL') or self.DEFAULT_MODEL).strip() or self.DEFAULT_MODEL

    def _resolve_model(self, user: Optional[User]) -> str:
        model = self._preferences(user).get('ai_model')
        if isinstance(model, str) and model.strip():
            return model.strip()
        return self._default_model()

    @staticmethod
    def _mask_credential(value: Optional[str], fallback: str = '') -> str:
        if not value:
            return fallback
        cleaned = value.strip()
        if len(cleaned) <= 8:
            return '*' * len(cleaned)
        return f'{cleaned[:4]}...{cleaned[-4:]}'

    @classmethod
    def is_real_key(cls, value: Optional[str]) -> bool:
        cleaned = (value or '').strip()
        if len(cleaned) < 10:
            return False
        lowered = cleaned.lower()
        return not any(marker in lowered for marker in cls.PLACEHOLDER_KEY_MARKERS)

    @staticmethod
    def _normalize_base_url(base_url: Optional[str]) -> str:
        default_base = current_app.config.get('AI_BASE_URL') or 'https://api.deepseek.com'
        return (base_url or default_base or '').strip().rstrip('/')

    def _external_diagnostics(self, api_key: Optional[str], base_url: str) -> Dict[str, Any]:
        if not api_key:
            return {
                'configured': False,
                'reachable': None,
                'status': 'not_configured',
                'message': '尚未配置外部推理服务凭证。',
                'latency_ms': None,
            }
        cache_key = f'{base_url}:{self._mask_credential(api_key)}'
        cached = self._diagnostic_cache.get(cache_key)
        now = time()
        cache_ttl = int(current_app.config.get('AI_DIAGNOSTICS_CACHE_SECONDS', 60))
        if cached and now - cached['checked_at'] < cache_ttl:
            return {
                **cached['result'],
                'cached': True,
                'cache_age_seconds': int(now - cached['checked_at']),
            }
        endpoint = base_url if base_url.endswith('/v1') else f'{base_url}/v1'
        started = perf_counter()
        try:
            client = self._get_http_client()
            diagnostic_timeout = min(float(current_app.config.get('AI_DIAGNOSTICS_TIMEOUT_SECONDS', 2.0)), float(current_app.config.get('AI_REQUEST_TIMEOUT_SECONDS', self.timeout)))
            response = client.get(
                f'{endpoint}/models',
                headers={'Authorization': f'Bearer {api_key}'},
                timeout=diagnostic_timeout
            )
            reachable = response.status_code < 500
            latency_ms = int(max((perf_counter() - started) * 1000, 0))
            if response.status_code == 200:
                result = {
                    'configured': True,
                    'reachable': True,
                    'status': 'ready',
                    'message': '外部推理服务连接正常。',
                    'latency_ms': latency_ms,
                }
                self._diagnostic_cache[cache_key] = {'checked_at': now, 'result': result}
                return result
            if response.status_code in (401, 403):
                result = {
                    'configured': True,
                    'reachable': True,
                    'status': 'credential_invalid',
                    'message': '外部推理服务已连接，但凭证校验未通过。',
                    'latency_ms': latency_ms,
                }
                self._diagnostic_cache[cache_key] = {'checked_at': now, 'result': result}
                return result
            result = {
                'configured': True,
                'reachable': reachable,
                'status': 'degraded',
                'message': f'外部推理服务返回状态 {response.status_code}。',
                'latency_ms': latency_ms,
            }
            self._diagnostic_cache[cache_key] = {'checked_at': now, 'result': result}
            return result
        except Exception as exc:
            result = {
                'configured': True,
                'reachable': False,
                'status': 'unreachable',
                'message': f'外部推理服务当前不可达：{str(exc)}',
                'latency_ms': int(max((perf_counter() - started) * 1000, 0)),
            }
            self._diagnostic_cache[cache_key] = {'checked_at': now, 'result': result}
            return result
    
    def is_configured(self, user: Optional[User] = None) -> bool:
        user_key, _ = self._resolve_user_credentials(user)
        if self.is_real_key(user_key):
            return True
        
        default_key, _ = self._get_credentials()
        return self.is_real_key(default_key)
    
    @staticmethod
    def _resolve_user_credentials(user: Optional[User]) -> Tuple[Optional[str], Optional[str]]:
        if not user:
            return None, None
        prefs = user.preferences or {}
        if not isinstance(prefs, dict):
            return None, None
        return prefs.get('ai_api_key'), prefs.get('ai_api_base')

    def get_settings(self, user: Optional[User] = None) -> Dict[str, Any]:
        prefs = self._preferences(user)
        user_key, user_base = self._resolve_user_credentials(user)
        default_key, _ = self._get_credentials()
        base_url = self._normalize_base_url(user_base)
        has_user_key = self.is_real_key(user_key)
        has_system_key = self.is_real_key(default_key)
        external_source = 'user' if has_user_key else 'system' if has_system_key else 'none'
        masked = self._mask_credential(user_key) if has_user_key else '系统托管' if has_system_key else ''
        return {
            'analysis_mode': self._resolve_mode(user),
            'local_analysis_enabled': bool(current_app.config.get('AI_LOCAL_ANALYSIS', False)),
            'external_configured': has_user_key or has_system_key,
            'external_source': external_source,
            'external_base': base_url,
            'credential_masked': masked,
            'model': self._resolve_model(user),
            'can_use_local': bool(current_app.config.get('AI_LOCAL_ANALYSIS', False)),
            'has_user_credential': has_user_key,
            'preferences_updated_at': user.updated_at.isoformat() if getattr(user, 'updated_at', None) else None,
            'dashboard_scope': prefs.get('analysis_scope', 'operations'),
        }

    def update_settings(self, user: User, payload: Dict[str, Any]) -> Dict[str, Any]:
        prefs = dict(self._preferences(user))
        mode = (payload.get('analysis_mode') or '').strip()
        if mode in self.VALID_MODES:
            prefs['analysis_mode'] = mode

        base_url = payload.get('ai_api_base')
        if base_url is not None:
            cleaned = str(base_url).strip()
            if cleaned:
                prefs['ai_api_base'] = cleaned
            else:
                prefs.pop('ai_api_base', None)

        dashboard_scope = payload.get('analysis_scope')
        if dashboard_scope in {'operations', 'finance', 'supply', 'fulfillment'}:
            prefs['analysis_scope'] = dashboard_scope

        model = payload.get('ai_model', payload.get('model'))
        if model is not None:
            cleaned = str(model).strip()
            if cleaned:
                if not re.fullmatch(r'[A-Za-z0-9._:/-]{2,96}', cleaned):
                    raise ValueError('模型名称只能包含字母、数字、点、横线、下划线、斜杠或冒号。')
                prefs['ai_model'] = cleaned
            else:
                prefs.pop('ai_model', None)

        credential = payload.get('ai_api_key')
        if credential is not None:
            cleaned = str(credential).strip()
            if cleaned:
                prefs['ai_api_key'] = cleaned
            else:
                prefs.pop('ai_api_key', None)

        user.preferences = prefs
        return self.get_settings(user)

    def run_diagnostics(self, user: Optional[User] = None) -> Dict[str, Any]:
        settings = self.get_settings(user)
        user_key, user_base = self._resolve_user_credentials(user)
        api_key, base_url = self._get_credentials(api_key=user_key, base_url=user_base)
        snapshot = self.operations_snapshot(limit=5)
        external = self._external_diagnostics(api_key if settings['analysis_mode'] != 'local' else None, self._normalize_base_url(base_url))
        local_ready = bool(current_app.config.get('AI_LOCAL_ANALYSIS', False))
        if settings['analysis_mode'] == 'external' and not external['configured']:
            overall = 'attention'
        elif external['status'] in {'unreachable', 'credential_invalid'} and settings['analysis_mode'] != 'local':
            overall = 'degraded'
        else:
            overall = 'ready' if local_ready or external['reachable'] else 'attention'
        return {
            'overall_status': overall,
            'analysis_mode': settings['analysis_mode'],
            'local': {
                'available': local_ready,
                'status': 'ready' if local_ready else 'disabled',
                'message': '内置经营分析已就绪。' if local_ready else '当前未启用内置经营分析。',
            },
            'external': {
                **external,
                'base': settings['external_base'],
                'source': settings['external_source'],
                'credential_masked': settings['credential_masked'],
            },
            'snapshot': {
                'low_stock_count': snapshot['low_stock_count'],
                'pending_purchase_count': snapshot['pending_purchase_count'],
                'overdue_receivable_count': snapshot['overdue_receivable_count'],
                'overdue_amount': snapshot['overdue_amount'],
                'recent_report_count': len(snapshot['recent_reports']),
            },
            'sample_actions': [
                {'title': '补货建议', 'metric': f"{snapshot['low_stock_count']} 项", 'path': '/app/inventory/replenishment'},
                {'title': '采购审批', 'metric': f"{snapshot['pending_purchase_count']} 单", 'path': '/app/procurement/orders'},
                {'title': '收款跟进', 'metric': f"{snapshot['overdue_receivable_count']} 笔", 'path': '/app/finance/receivables'},
            ],
        }

    def structured_operations_analysis(self, scenario: str = 'daily_brief', limit: int = 8, user: Optional[User] = None) -> Dict[str, Any]:
        snapshot = self.operations_snapshot(limit=max(limit, 4))
        concern = {
            'inventory': '库存与补货',
            'procurement': '采购与收货',
            'receivables': '应收与信用',
            'daily_brief': '当班经营总览',
        }.get(scenario, '经营总览')

        insight_cards = [
            {
                'title': '低库存对象',
                'metric': f"{snapshot['low_stock_count']} 项",
                'note': '优先锁定会影响本周履约的物料。',
                'tone': 'warning' if snapshot['low_stock_count'] else 'success',
                'path': '/app/inventory/replenishment',
            },
            {
                'title': '待审批采购',
                'metric': f"{snapshot['pending_purchase_count']} 单",
                'note': '采购审批与收货节奏决定补货恢复速度。',
                'tone': 'warning' if snapshot['pending_purchase_count'] else 'success',
                'path': '/app/procurement/orders',
            },
            {
                'title': '逾期应收',
                'metric': f"{snapshot['overdue_receivable_count']} 笔",
                'note': f"未收金额 {snapshot['overdue_amount']:.2f} 元。",
                'tone': 'danger' if snapshot['overdue_receivable_count'] else 'success',
                'path': '/app/finance/receivables',
            },
        ]

        action_items = []
        if snapshot['low_stock']:
            item = snapshot['low_stock'][0]
            action_items.append({
                'title': f"优先补 {item['name']}",
                'description': f"{item['sku']} 当前 {item['quantity']}，安全线 {item['min_stock']}，建议先补齐缺口。",
                'priority': 'high',
                'path': '/app/inventory/replenishment',
                'prompt': '请生成低库存物料的补货执行摘要。',
            })
        if snapshot['pending_purchase']:
            item = snapshot['pending_purchase'][0]
            action_items.append({
                'title': f"推进采购单 {item['po_no']}",
                'description': f"供应商 {item['supplier']}，金额 {item['amount']:.2f} 元，建议确认审批和到货时间。",
                'priority': 'high',
                'path': '/app/procurement/orders',
                'prompt': '请生成采购审批摘要，并说明收货前置条件。',
            })
        if snapshot['overdue_receivables']:
            item = snapshot['overdue_receivables'][0]
            action_items.append({
                'title': f"跟进应收 {item['receivable_no']}",
                'description': f"{item['customer']} 尚未收回 {item['unpaid']:.2f} 元，建议同步催款和信用控制。",
                'priority': 'high',
                'path': '/app/finance/receivables',
                'prompt': '请生成催款跟进话术，并说明信用冻结条件。',
            })
        if not action_items:
            action_items.append({
                'title': '生成经营日报',
                'description': '当前异常较少，可整理库存、采购、履约和收款结果进入日报。',
                'priority': 'normal',
                'path': '/app/reports',
                'prompt': '请生成管理层经营日报摘要。',
            })

        scenario_summary = {
            'inventory': '重点关注低库存、补货建议与采购收货衔接。',
            'procurement': '优先处理待审批采购和收货阻塞，避免影响工厂仓恢复。',
            'receivables': '围绕逾期应收、信用占用和催款节奏安排动作。',
            'daily_brief': '围绕低库存、采购审批、履约发货和收款进展安排当班动作。',
        }.get(scenario, '按库存、采购、履约和收款四条主线推进。')

        return {
            'scenario': scenario,
            'headline': concern,
            'summary': scenario_summary,
            'generated_at': utcnow().isoformat(),
            'insight_cards': insight_cards,
            'action_items': action_items,
            'related_records': {
                'low_stock': snapshot['low_stock'][:limit],
                'pending_purchase': snapshot['pending_purchase'][:limit],
                'overdue_receivables': snapshot['overdue_receivables'][:limit],
                'recent_reports': snapshot['recent_reports'][: min(limit, 4)],
            },
        }
    
    def chat(
        self, 
        message: str, 
        user: Optional[User] = None,
        context: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None
    ) -> Dict:
        try:
            mode = self._resolve_mode(user)
            model = self._resolve_model(user)
            user_api_key, user_base = self._resolve_user_credentials(user)
            api_key, base_url = self._get_credentials(api_key=user_api_key, base_url=user_base)
            can_use_local = current_app.config.get('AI_LOCAL_ANALYSIS', False) and mode in {'local', 'hybrid'}
            should_use_external = mode in {'external', 'hybrid'} and bool(api_key)

            if not should_use_external:
                if can_use_local:
                    try:
                        text_context = f"{message} {' '.join([c.get('content', '') for c in (context or [])])}"
                        if any(keyword in text_context for keyword in ['库存', '盘点', '补货', '采购', '应收', '履约', '报表']):
                            content = self.local_operations_reply(text_context, user=user)
                        else:
                            content = self.local_operations_reply(message, user=user)

                        return {
                            "success": True,
                            "content": content,
                            "usage": {},
                            "error": None,
                            "source": "operations_engine",
                            "provider_warning": None,
                        }
                    except Exception as e:
                        return {
                            "success": False,
                            "content": "",
                            "usage": {},
                            "error": f"经营分析失败: {str(e)}"
                        }

                return {
                    "success": False,
                    "content": "",
                    "usage": {},
                    "error": "当前分析模式要求外部推理服务，但尚未完成服务配置。",
                    "source": "analysis_provider"
                }
            
            messages = []
            
            if not system_prompt:
                system_prompt = """你是 NEXUS PRIME 经营分析助手。
只基于系统内库存、采购、销售履约、应收、报表和审计数据回答。
输出要包含风险、依据、建议动作和关联页面，不编造系统没有的数据。"""
            
            messages.append({"role": "system", "content": system_prompt})
            
            if context:
                messages.extend(context[-10:])
            
            messages.append({"role": "user", "content": message})
            
            client = self._get_http_client()
            
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
                    "model": model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 2000,
                    "stream": False
                }
            )
            
            if response.status_code != 200:
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = error_json.get('error', {}).get('message', error_detail)
                except:
                    pass
                raise Exception(f"API 返回错误 ({response.status_code}): {error_detail}")
            
            result = response.json()
            assistant_message = result['choices'][0]['message']['content']
            usage = result.get('usage', {})
            
            self._save_chat_log(getattr(user, 'id', None), message, assistant_message, usage, model)
            
            return {
                "success": True,
                "content": assistant_message,
                "usage": {
                    "prompt_tokens": usage.get('prompt_tokens', 0),
                    "completion_tokens": usage.get('completion_tokens', 0),
                    "total_tokens": usage.get('total_tokens', 0)
                },
                "error": None,
                "source": "analysis_provider",
                "provider_warning": None,
            }
            
        except httpx.TimeoutException:
            if locals().get('can_use_local'):
                return {
                    "success": True,
                    "content": self.local_operations_reply(message, user=user),
                    "usage": {},
                    "error": "外部分析服务响应超时，已使用本地经营引擎完成分析。",
                    "source": "operations_engine",
                    "provider_warning": "外部分析服务响应超时，已使用本地经营引擎完成分析。",
                }
            return {
                "success": False,
                "content": "",
                "usage": {},
                "error": "分析服务响应超时，请稍后重试。",
                "source": "analysis_provider"
            }
        except httpx.ConnectError:
            if locals().get('can_use_local'):
                return {
                    "success": True,
                    "content": self.local_operations_reply(message, user=user),
                    "usage": {},
                    "error": "无法连接到外部分析服务，已使用本地经营引擎完成分析。",
                    "source": "operations_engine",
                    "provider_warning": "无法连接到外部分析服务，已使用本地经营引擎完成分析。",
                }
            return {
                "success": False,
                "content": "",
                "usage": {},
                "error": "无法连接到分析服务，请检查网络连接。",
                "source": "analysis_provider"
            }
        except Exception as e:
            error_msg = str(e)
            current_app.logger.error(f"Analysis provider error: {error_msg}")
            
            if 'api_key' in error_msg.lower() or 'authentication' in error_msg.lower() or '401' in error_msg:
                friendly_error = "分析服务凭证无效或已过期，请联系管理员检查配置。"
            elif 'timeout' in error_msg.lower():
                friendly_error = "分析服务响应超时，请稍后重试。"
            elif 'connection' in error_msg.lower():
                friendly_error = "无法连接到分析服务，请检查网络连接。"
            else:
                friendly_error = f"分析服务暂时不可用: {error_msg}"

            if locals().get('can_use_local'):
                return {
                    "success": True,
                    "content": self.local_operations_reply(message, user=user),
                    "usage": {},
                    "error": f"{friendly_error} 已使用本地经营引擎完成分析。",
                    "source": "operations_engine",
                    "provider_warning": f"{friendly_error} 已使用本地经营引擎完成分析。",
                }
            
            return {
                "success": False,
                "content": "",
                "usage": {},
                "error": friendly_error,
                "source": "analysis_provider"
            }
    
    def _save_chat_log(self, user_id: Optional[int], user_msg: str, ai_msg: str, usage: dict, model: Optional[str] = None):
        try:
            from app.models.sys import AiChatLog
            
            log = AiChatLog(
                user_id=user_id,
                prompt=user_msg,
                response=ai_msg,
                model_version=(model or self._default_model())[:32]
            )
            db.session.add(log)
            db.session.commit()
        except ImportError:
            pass
        except Exception as e:
            current_app.logger.warning(f"Failed to save chat log: {str(e)}")
            db.session.rollback()
    
    def local_operations_reply(self, message: str, user: Optional[User] = None) -> str:
        snapshot = self.operations_snapshot(limit=6)
        concern = "综合经营"
        if '库存' in message or '补货' in message or '盘点' in message:
            concern = "库存与补货"
        elif '应收' in message or '催款' in message or '信用' in message:
            concern = "应收与信用"
        elif '采购' in message or '收货' in message:
            concern = "采购与收货"
        elif '履约' in message or '发货' in message:
            concern = "销售履约"

        low_stock = snapshot['low_stock']
        overdue = snapshot['overdue_receivables']
        pending_purchase = snapshot['pending_purchase']
        draft_reports = snapshot['recent_reports']

        lines = [
            f"【{concern}摘要】",
            f"- 低水位物料：{snapshot['low_stock_count']} 项；优先查看 /app/inventory/replenishment。",
            f"- 待审批采购：{snapshot['pending_purchase_count']} 单；优先查看 /app/procurement/orders。",
            f"- 逾期应收：{snapshot['overdue_receivable_count']} 笔，未收金额 {snapshot['overdue_amount']:.2f}；优先查看 /app/finance/receivables。",
            "",
            "【优先动作】",
        ]

        if low_stock:
            item = low_stock[0]
            lines.append(f"1. 将 {item['sku']} {item['name']} 转为补货建议，当前库存 {item['quantity']}，安全线 {item['min_stock']}。")
        else:
            lines.append("1. 库存水位暂未出现低于安全线的物料，建议复核高周转物料的补货提前期。")

        if pending_purchase:
            item = pending_purchase[0]
            lines.append(f"2. 处理采购单 {item['po_no']}，供应商 {item['supplier']}，金额 {item['amount']:.2f}。")
        else:
            lines.append("2. 当前没有待审批采购单，可重点检查在途收货和供应商准点率。")

        if overdue:
            item = overdue[0]
            lines.append(f"3. 跟进 {item['customer']} 的应收 {item['receivable_no']}，未收 {item['unpaid']:.2f}，必要时联动信用控制。")
        else:
            lines.append("3. 应收逾期压力较低，可继续关注大额未到期客户的信用占用。")

        if draft_reports:
            lines.append(f"4. 最近报表 {draft_reports[0]['name']} 已可复核归档，确认后进入文件资料库。")
        else:
            lines.append("4. 生成库存、采购、应收联合日报，作为班次复盘材料。")

        lines.extend([
            "",
            "【追踪建议】",
            "执行后检查库存流水、采购状态、收款记录和审计日志，确保动作与数据库记录一致。"
        ])
        return "\n".join(lines)

    def operations_snapshot(self, limit: int = 6) -> Dict:
        from sqlalchemy import func
        from app.models.biz import Product, Partner
        from app.models.finance import Receivable
        from app.models.notification import GeneratedReport, StockAlert
        from app.models.purchase import PurchaseOrder
        from app.models.stock import Stock

        qty_expr = func.coalesce(func.sum(Stock.quantity), 0)
        low_rows = (
            db.session.query(Product, qty_expr.label('qty'))
            .outerjoin(Stock, Stock.product_id == Product.id)
            .filter(Product.is_deleted == False)
            .group_by(Product.id)
            .having(qty_expr < Product.min_stock)
            .order_by((Product.min_stock - qty_expr).desc())
            .limit(limit)
            .all()
        )
        purchase_rows = (
            PurchaseOrder.query
            .filter_by(is_deleted=False, status=PurchaseOrder.STATUS_PENDING)
            .order_by(PurchaseOrder.total_amount.desc())
            .limit(limit)
            .all()
        )
        receivable_rows = (
            Receivable.query
            .filter(Receivable.is_deleted == False, Receivable.status == Receivable.STATUS_OVERDUE)
            .order_by((Receivable.total_amount - Receivable.paid_amount).desc())
            .limit(limit)
            .all()
        )
        reports = (
            GeneratedReport.query
            .filter_by(is_deleted=False)
            .order_by(GeneratedReport.generated_at.desc())
            .limit(limit)
            .all()
        )

        def partner_name(customer_id):
            partner = db.session.get(Partner, customer_id) if customer_id else None
            return partner.name if partner else '未关联客户'

        overdue_amount = sum(float((row.total_amount or 0) - (row.paid_amount or 0)) for row in receivable_rows)
        return {
            'low_stock_count': StockAlert.query.filter_by(is_deleted=False, status=StockAlert.STATUS_ACTIVE).count() or len(low_rows),
            'pending_purchase_count': PurchaseOrder.query.filter_by(is_deleted=False, status=PurchaseOrder.STATUS_PENDING).count(),
            'overdue_receivable_count': Receivable.query.filter_by(is_deleted=False, status=Receivable.STATUS_OVERDUE).count(),
            'overdue_amount': overdue_amount,
            'low_stock': [
                {'sku': product.sku, 'name': product.name, 'quantity': int(qty or 0), 'min_stock': int(product.min_stock or 0)}
                for product, qty in low_rows
            ],
            'pending_purchase': [
                {'po_no': row.po_no, 'supplier': row.supplier.name if row.supplier else '未关联供应商', 'amount': float(row.total_amount or 0)}
                for row in purchase_rows
            ],
            'overdue_receivables': [
                {
                    'receivable_no': row.receivable_no,
                    'customer': partner_name(row.customer_id),
                    'unpaid': float((row.total_amount or 0) - (row.paid_amount or 0)),
                }
                for row in receivable_rows
            ],
            'recent_reports': [
                {'name': row.report_name, 'type': row.report_type}
                for row in reports
            ],
        }

    def analyze_inventory(self, limit: int = 10, user: Optional[User] = None) -> str:
        try:
            snapshot = self.operations_snapshot(limit=limit)
            lines = [
                "【库存风险摘要】",
                f"- 低水位物料 {snapshot['low_stock_count']} 项，待审批采购 {snapshot['pending_purchase_count']} 单。",
                f"- 逾期应收 {snapshot['overdue_receivable_count']} 笔，未收金额 {snapshot['overdue_amount']:.2f}，可能影响信用销售。",
                "",
                "【低库存清单】",
            ]
            if snapshot['low_stock']:
                for index, item in enumerate(snapshot['low_stock'][:limit], 1):
                    gap = max(int(item['min_stock']) - int(item['quantity']), 0)
                    lines.append(f"{index}. {item['sku']} {item['name']}：当前 {item['quantity']}，安全线 {item['min_stock']}，建议补足缺口 {gap} 后再按交期放大。")
            else:
                lines.append("当前没有低于安全线的物料，建议复核高周转 SKU 的最大库存和供应商交期。")

            lines.extend(["", "【执行顺序】"])
            if snapshot['pending_purchase']:
                top_po = snapshot['pending_purchase'][0]
                lines.append(f"1. 先审批 {top_po['po_no']}，供应商 {top_po['supplier']}，金额 {top_po['amount']:.2f}。")
            else:
                lines.append("1. 采购审批队列为空，优先检查补货建议是否需要转采购。")
            lines.append("2. 收货后复核库存流水和库位，避免账实差异进入盘点阶段。")
            lines.append("3. 对受低库存影响的销售订单设置发货优先级，并同步客户窗口。")
            return "\n".join(lines)
            
        except Exception as e:
            return f"库存分析失败: {str(e)}"
    
    def generate_report(self, report_type: str, data: Dict, user: Optional[User] = None) -> str:
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


ai_service = AIService()
