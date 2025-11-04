"""
Vercel Serverless Function入口
适配Vercel的Serverless架构
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入Flask应用
from app import app

# Vercel Python运行时需要导出app对象
# 它会自动处理Flask应用的WSGI接口
handler = app

