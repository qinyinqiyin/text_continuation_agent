# 服务器端服务建议

## 当前架构分析

### ✅ 优点
- **简单快速**：无数据库依赖，部署简单
- **轻量级**：适合个人项目或Demo
- **低成本**：无需数据库服务费用

### ⚠️ 限制
- **数据不持久化**：Serverless环境重启后数据丢失
- **无用户隔离**：所有用户共享同一个知识库
- **无认证机制**：任何人都可以访问和修改数据
- **API密钥暴露**：密钥在前端传递，存在安全风险
- **无使用限制**：无法防止滥用

---

## 是否需要添加服务器端服务？

### 场景1：个人使用或Demo ✅ **不需要**

**适用情况**：
- 个人使用
- 演示项目
- 快速原型

**建议**：保持当前架构，简单高效

---

### 场景2：多人使用或生产环境 ⚠️ **建议添加**

**适用情况**：
- 多个用户需要独立的知识库
- 需要数据持久化
- 需要防止滥用
- 需要保护API密钥

**建议添加的功能**：

#### 🔐 1. 用户认证系统（高优先级）

**为什么需要**：
- 每个用户独立的知识库
- 防止数据被他人修改
- 保护用户隐私

**实现方案**：
```python
# 简单的Session认证
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
app.config['SESSION_TYPE'] = 'filesystem'  # 或使用Redis
Session(app)
```

**或使用JWT**：
```python
import jwt
from functools import wraps

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        # 验证token
        return f(*args, **kwargs)
    return decorated
```

---

#### 💾 2. 数据库存储（高优先级）

**为什么需要**：
- 数据持久化（Serverless环境数据会丢失）
- 多用户数据隔离
- 知识库持久保存

**推荐方案**：

**选项A：SQLite（简单）**
```python
import sqlite3
from flask import g

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect('knowledge_base.db')
    return db
```

**选项B：PostgreSQL（推荐，Render免费）**
```python
# Render提供免费PostgreSQL数据库
import psycopg2
DATABASE_URL = os.getenv('DATABASE_URL')  # Render自动提供
```

**选项C：MongoDB（适合文档存储）**
```python
from pymongo import MongoClient
client = MongoClient(os.getenv('MONGODB_URI'))
db = client.text_continuation_db
```

---

#### 🛡️ 3. API密钥管理（高优先级）

**当前问题**：
- API密钥在前端传递，可能被泄露
- 无法统一管理

**解决方案**：
```python
# 服务器端存储API密钥（加密）
from cryptography.fernet import Fernet

class APIKeyManager:
    def __init__(self):
        self.cipher = Fernet(os.getenv('ENCRYPTION_KEY'))
    
    def store_key(self, user_id, api_key):
        encrypted = self.cipher.encrypt(api_key.encode())
        # 存储到数据库
        db.save_user_api_key(user_id, encrypted)
    
    def get_key(self, user_id):
        encrypted = db.get_user_api_key(user_id)
        return self.cipher.decrypt(encrypted).decode()
```

---

#### 📊 4. API限流（中优先级）

**为什么需要**：
- 防止滥用
- 控制成本
- 保护服务稳定性

**实现方案**：
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["100 per hour"]
)

@app.route('/api/continuation', methods=['POST'])
@limiter.limit("10 per minute")
def continuation():
    # ...
```

---

#### 👥 5. 多用户支持（中优先级）

**实现方案**：
```python
# 每个用户独立的知识库
def get_user_knowledge_base(user_id):
    kb = FAISSKnowledgeBase(
        model_name="bert-base-chinese",
        cache_file=f"kb_user_{user_id}.pkl"
    )
    return kb
```

---

## 推荐实施方案

### 🥇 方案1：最小化改进（适合快速上线）

**添加**：
1. ✅ SQLite数据库（知识库持久化）
2. ✅ 简单的Session认证（可选）
3. ✅ API密钥服务器端存储

**工作量**：1-2天
**成本**：免费

---

### 🥈 方案2：完整方案（适合生产环境）

**添加**：
1. ✅ PostgreSQL数据库（Render免费）
2. ✅ JWT用户认证
3. ✅ 多用户支持
4. ✅ API限流
5. ✅ 服务器端API密钥管理

**工作量**：3-5天
**成本**：免费（使用Render免费PostgreSQL）

---

## 快速实现示例

### 添加SQLite数据库

```python
# database.py
import sqlite3
import os
from contextlib import contextmanager

class Database:
    def __init__(self, db_path='knowledge_base.db'):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                type TEXT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    
    @contextmanager
    def get_conn(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
```

### 修改知识库使用数据库

```python
# knowledge_base.py
class FAISSKnowledgeBase:
    def __init__(self, user_id=None, db=None):
        # ...
        self.user_id = user_id or "default"
        self.db = db
    
    def add_setting(self, setting_type, content):
        # 保存到数据库
        if self.db:
            with self.db.get_conn() as conn:
                conn.execute(
                    'INSERT INTO settings (user_id, type, content) VALUES (?, ?, ?)',
                    (self.user_id, setting_type, content)
                )
        # 原有的向量索引逻辑
        # ...
```

---

## 建议优先级

### 🔴 高优先级（建议立即添加）

1. **数据库持久化**
   - 原因：Serverless环境数据会丢失
   - 实现：SQLite或PostgreSQL
   - 时间：1-2小时

2. **API密钥服务器端存储**
   - 原因：安全考虑
   - 实现：加密存储到数据库
   - 时间：2-3小时

### 🟡 中优先级（根据需求添加）

3. **用户认证**
   - 原因：多用户支持
   - 实现：Session或JWT
   - 时间：1天

4. **API限流**
   - 原因：防止滥用
   - 实现：Flask-Limiter
   - 时间：1小时

### 🟢 低优先级（可选）

5. **多租户支持**
   - 原因：独立知识库
   - 实现：按user_id隔离
   - 时间：1天

---

## 总结建议

### 如果只是个人使用或Demo：
**不需要**添加复杂的服务器端服务，当前架构足够。

### 如果要多人使用或生产环境：
**建议添加**：
1. ✅ 数据库持久化（必须）
2. ✅ API密钥服务器端管理（推荐）
3. ⚠️ 用户认证（如果多人使用）
4. ⚠️ API限流（防止滥用）

### 最简单的改进：
**添加SQLite数据库**即可解决数据持久化问题，成本低，实现简单。

---

## 快速开始

### 最小化改进（30分钟）

1. 添加SQLite数据库
2. 修改知识库保存逻辑
3. 测试数据持久化

### 完整方案（2-3天）

1. 设置PostgreSQL数据库
2. 实现用户认证
3. 添加API限流
4. 实现多用户支持

**需要我帮你实现哪种方案？**

