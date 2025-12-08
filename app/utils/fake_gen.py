import random
from faker import Faker
from faker.providers import BaseProvider

class NexusProvider(BaseProvider):
    """
    NEXUS 专用数据生成器
    生成具有科技感、未来感的专有名词
    """
    
    # 科技前缀
    tech_prefixes = [
        '量子', '纳米', '光子', '暗物质', '聚变', '全息', '神经网络', 
        '赛博', '泰坦', '幽灵', '等离子', '超导', '零点', '引力波',
        '星际', '虚空', '反物质', '高能', '脉冲', '相位'
    ]
    
    # 产品后缀
    product_suffixes = [
        '计算终端', '推进器', '存储晶体', '修复液', '外骨骼', 
        '护盾发生器', '无人机', '处理器', '传感器矩阵', '动力核心',
        '生物芯片', '光学迷彩', '机械臂', '控制中枢', '转换器', '装甲片'
    ]
    
    # 公司后缀
    company_suffixes = [
        '重工', '动力', '生物科技', '实验室', '工业', 
        '防务', '系统', '网络', '矩阵', '探索公司', '联合体'
    ]

    # 部门名称
    dept_names = [
        '中央指挥部', '特种作战部', '后勤保障部', 
        '研发实验室', '深空探索部', '财务审计局', '人力资源部'
    ]

    def tech_product_name(self):
        """生成科技产品名"""
        return f"{self.random_element(self.tech_prefixes)}{self.random_element(self.product_suffixes)}"

    def sci_fi_company(self):
        """生成科技公司名"""
        prefix = self.generator.last_name() # 使用 Faker 内置的姓氏作为公司名
        return f"{prefix}{self.random_element(self.company_suffixes)}"

    def nexus_department(self):
        return self.random_element(self.dept_names)

# 初始化 Faker 并添加自定义 Provider
fake = Faker('zh_CN')
fake.add_provider(NexusProvider)