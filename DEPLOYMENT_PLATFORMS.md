# 免费部署平台对比指南

## 为什么Vercel有内存限制？

### 技术原因
1. **Serverless架构**：Vercel使用Serverless Functions，每个函数都是独立的容器
   - 容器内存固定，便于资源调度
   - 冷启动优化需要预设内存大小
   - 多租户隔离需要资源限制

2. **成本控制**：
   - 防止资源滥用
   - 确保平台稳定运行
   - 免费用户享受优质服务

3. **公平性**：
   - 防止单个用户占用过多资源
   - 保证所有用户的服务质量

### Vercel的限制
- **免费版**：1024MB内存/函数，60秒执行时间
- **Pro版**：3000MB内存/函数，300秒执行时间
- **构建时**：内存限制更严格，容易OOM

---

## 免费部署平台对比

### 🌟 推荐：适合Python Flask应用

| 平台 | 内存限制 | 构建限制 | 适合场景 | 推荐度 |
|------|---------|---------|---------|--------|
| **Railway** | 512MB免费 | 较宽松 | 小型应用 | ⭐⭐⭐⭐⭐ |
| **Render** | 512MB免费 | 中等 | 中型应用 | ⭐⭐⭐⭐ |
| **Fly.io** | 256MB免费 | 宽松 | 轻量应用 | ⭐⭐⭐⭐ |
| **Heroku** | 512MB（已取消免费） | - | - | ❌ |
| **Google Cloud Run** | 512MB免费 | 宽松 | 容器化应用 | ⭐⭐⭐⭐⭐ |
| **AWS Lambda** | 10240MB | 严格 | Serverless | ⭐⭐⭐ |
| **DigitalOcean App Platform** | 512MB免费 | 中等 | 简单应用 | ⭐⭐⭐ |

---

## 详细平台介绍

### 1. Railway ⭐⭐⭐⭐⭐

**优点**：
- ✅ 内存限制宽松（512MB免费，可升级）
- ✅ 构建时内存充足，很少OOM
- ✅ 自动部署，Git集成
- ✅ 支持Python、Node.js等
- ✅ 每月$5免费额度（足够小型项目）

**缺点**：
- ⚠️ 免费额度有限，超出需付费
- ⚠️ 文档相对较少

**适用场景**：
- 需要稳定运行的应用
- 小型到中型项目
- 需要数据库的项目

**配置示例**：
```python
# Procfile（如果使用）
web: gunicorn app:app

# requirements.txt
gunicorn>=21.2.0
flask>=2.3.0
```

**部署步骤**：
1. 访问 https://railway.app
2. 连接GitHub仓库
3. 自动检测Python项目
4. 配置环境变量
5. 自动部署

---

### 2. Render ⭐⭐⭐⭐

**优点**：
- ✅ 免费层512MB内存
- ✅ 自动SSL证书
- ✅ 持续部署
- ✅ 支持PostgreSQL数据库（免费）
- ✅ 文档完善

**缺点**：
- ⚠️ 免费服务有冷启动（15分钟不活跃会休眠）
- ⚠️ 构建限制中等

**适用场景**：
- 个人项目
- 需要数据库的应用
- 不介意冷启动的应用

**配置示例**：
```yaml
# render.yaml
services:
  - type: web
    name: text-continuation-agent
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn app:app
    envVars:
      - key: FLASK_ENV
        value: production
```

**部署步骤**：
1. 访问 https://render.com
2. 创建Web Service
3. 连接GitHub仓库
4. 配置构建和启动命令
5. 部署

---

### 3. Fly.io ⭐⭐⭐⭐

**优点**：
- ✅ 全球边缘部署
- ✅ 内存可配置（256MB免费）
- ✅ 支持Docker
- ✅ 构建时资源充足
- ✅ 启动快速

**缺点**：
- ⚠️ 免费内存较小（256MB）
- ⚠️ 需要Docker知识

**适用场景**：
- 轻量级应用
- 需要全球部署
- 熟悉Docker

**配置示例**：
```dockerfile
# Dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080"]
```

---

### 4. Google Cloud Run ⭐⭐⭐⭐⭐

**优点**：
- ✅ 免费层512MB内存
- ✅ 按使用量付费（有免费额度）
- ✅ 自动扩缩容
- ✅ 支持Docker
- ✅ 构建资源充足
- ✅ Google云基础设施

**缺点**：
- ⚠️ 需要Google账号
- ⚠️ 配置稍复杂
- ⚠️ 需要绑定信用卡（但有免费额度）

**适用场景**：
- 生产环境应用
- 需要高可用性
- 熟悉云平台

**免费额度**：
- 每月200万请求
- 360,000 GB-秒内存
- 180,000 vCPU-秒

---

### 5. AWS Lambda（Serverless）⭐⭐⭐

**优点**：
- ✅ 内存可配置（最高10GB）
- ✅ 按使用量付费
- ✅ 高可用性
- ✅ 自动扩缩容

**缺点**：
- ⚠️ 需要适配Serverless架构
- ⚠️ 配置复杂
- ⚠️ 冷启动问题
- ⚠️ 执行时间限制

**适用场景**：
- Serverless架构应用
- 事件驱动应用
- 大企业项目

---

### 6. DigitalOcean App Platform ⭐⭐⭐

**优点**：
- ✅ 512MB免费内存
- ✅ 简单易用
- ✅ 自动部署

**缺点**：
- ⚠️ 免费层限制较多
- ⚠️ 需要信用卡验证

---

## 针对你的项目的建议

### 如果你的项目需要：
1. **向量检索功能** → 推荐 **Railway** 或 **Render**
   - 内存充足，构建稳定
   - 支持安装PyTorch等大型依赖

2. **快速部署，简单配置** → 推荐 **Railway**
   - 自动检测项目类型
   - 最少配置

3. **免费数据库** → 推荐 **Render**
   - 免费PostgreSQL数据库
   - 适合需要持久化的应用

4. **全球部署** → 推荐 **Fly.io**
   - 边缘部署，低延迟
   - 适合有国际用户的应用

5. **生产环境** → 推荐 **Google Cloud Run**
   - 高可用性
   - 专业基础设施

---

## 迁移指南

### 从Vercel迁移到Railway

1. **准备requirements.txt**
```txt
flask>=2.3.0
flask-cors>=4.0.0
gunicorn>=21.2.0
dashscope>=1.19.3
python-dotenv>=1.0.0
requests>=2.31.0
numpy>=1.24.0
# 可以安全添加torch等依赖
torch>=2.0.0
transformers>=4.30.0
faiss-cpu>=1.7.4
```

2. **创建Procfile**（可选）
```
web: gunicorn app:app --bind 0.0.0.0:$PORT
```

3. **修改app.py启动代码**
```python
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
```

4. **部署到Railway**
   - 连接GitHub仓库
   - Railway自动检测Python项目
   - 配置环境变量
   - 自动部署

---

## 各平台对比总结

| 特性 | Railway | Render | Fly.io | Cloud Run | Vercel |
|------|---------|--------|--------|-----------|--------|
| 免费内存 | 512MB | 512MB | 256MB | 512MB | 1024MB |
| 构建稳定性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| 易用性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 免费额度 | $5/月 | 有限 | 有限 | 充足 | 充足 |
| 冷启动 | 无 | 有 | 无 | 有 | 有 |
| 数据库 | 付费 | 免费 | 付费 | 付费 | 付费 |

---

## 推荐方案

### 🥇 首选：Railway
- **理由**：构建稳定，内存充足，配置简单
- **适合**：需要向量检索功能的项目
- **成本**：免费额度充足，超出按需付费

### 🥈 次选：Render
- **理由**：免费数据库，文档完善
- **适合**：需要持久化存储的项目
- **注意**：有冷启动问题

### 🥉 备选：Google Cloud Run
- **理由**：专业基础设施，高可用性
- **适合**：生产环境应用
- **注意**：需要绑定信用卡

---

## 快速开始

### Railway部署步骤：

1. **访问Railway**
   ```
   https://railway.app
   ```

2. **登录并创建项目**
   - 使用GitHub账号登录
   - 点击"New Project"
   - 选择"Deploy from GitHub repo"

3. **选择仓库**
   - 选择你的 `text_continuation_agent` 仓库
   - Railway自动检测Python项目

4. **配置环境变量**
   - 在项目设置中添加环境变量
   - `DASHSCOPE_API_KEY`: 你的API密钥
   - `FLASK_ENV`: `production`

5. **部署完成**
   - Railway自动构建和部署
   - 获得一个 `.railway.app` 域名

---

## 总结

- **Vercel的限制**：Serverless架构的必然结果，确保平台稳定
- **替代方案**：Railway、Render、Fly.io等都有更宽松的内存限制
- **推荐**：Railway最适合你的项目，构建稳定，支持大型依赖

选择合适的平台后，你的项目可以：
- ✅ 安装PyTorch等大型依赖
- ✅ 构建时不会OOM
- ✅ 正常运行向量检索功能

