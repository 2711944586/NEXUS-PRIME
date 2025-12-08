"""
验证码生成工具
支持生成随机验证码图片
"""
import random
import string
import base64
import io
import math

def generate_captcha_code(length=4):
    """生成随机验证码字符串（不包含容易混淆的字符）"""
    # 排除 0, O, I, 1, l 等容易混淆的字符
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(random.choice(chars) for _ in range(length))

def generate_captcha_svg(code):
    """生成SVG格式的验证码图片"""
    width = 120
    height = 40
    
    # 生成SVG
    svg_parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
    <defs>
        <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:#1a1a2e;stop-opacity:1" />
            <stop offset="100%" style="stop-color:#16213e;stop-opacity:1" />
        </linearGradient>
        <filter id="noise">
            <feTurbulence type="fractalNoise" baseFrequency="0.05" numOctaves="2" result="noise"/>
            <feDisplacementMap in="SourceGraphic" in2="noise" scale="3" xChannelSelector="R" yChannelSelector="G"/>
        </filter>
    </defs>
    <rect width="{width}" height="{height}" fill="url(#bg)"/>''']
    
    # 添加干扰线
    colors = ['#00d4ff', '#a855f7', '#22c55e', '#f59e0b', '#ef4444']
    for _ in range(5):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        color = random.choice(colors)
        svg_parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1" opacity="0.3"/>'
        )
    
    # 添加干扰点
    for _ in range(30):
        cx = random.randint(0, width)
        cy = random.randint(0, height)
        r = random.randint(1, 2)
        color = random.choice(colors)
        svg_parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}" opacity="0.5"/>'
        )
    
    # 添加验证码文字
    char_width = width // (len(code) + 1)
    for i, char in enumerate(code):
        x = char_width * (i + 0.7)
        y = height // 2 + random.randint(-3, 3)
        rotation = random.randint(-20, 20)
        color = random.choice(['#00d4ff', '#a855f7', '#22c55e'])
        font_size = random.randint(18, 22)
        
        svg_parts.append(
            f'<text x="{x}" y="{y}" font-family="Arial, sans-serif" font-size="{font_size}" '
            f'font-weight="bold" fill="{color}" transform="rotate({rotation},{x},{y})" '
            f'dominant-baseline="middle" filter="url(#noise)">{char}</text>'
        )
    
    # 添加额外的曲线干扰
    for _ in range(2):
        start_x = 0
        start_y = random.randint(10, 30)
        ctrl_x = random.randint(40, 80)
        ctrl_y = random.randint(5, 35)
        end_x = width
        end_y = random.randint(10, 30)
        color = random.choice(colors)
        svg_parts.append(
            f'<path d="M{start_x},{start_y} Q{ctrl_x},{ctrl_y} {end_x},{end_y}" '
            f'stroke="{color}" stroke-width="1.5" fill="none" opacity="0.4"/>'
        )
    
    svg_parts.append('</svg>')
    
    return ''.join(svg_parts)

def get_captcha_data_uri(code):
    """获取验证码的Data URI（用于直接嵌入HTML）"""
    svg_content = generate_captcha_svg(code)
    encoded = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
    return f'data:image/svg+xml;base64,{encoded}'

def create_captcha():
    """创建验证码，返回 (code, data_uri)"""
    code = generate_captcha_code()
    data_uri = get_captcha_data_uri(code)
    return code, data_uri
