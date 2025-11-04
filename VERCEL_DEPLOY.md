# Vercel部署指南

## 概述

本指南将帮助你使用Vercel部署文本续写助手项目。

## Vercel特点

- ✅ **免费额度**：每月100GB带宽，Serverless Functions
- ✅ **自动HTTPS**：自动配置SSL证书
- ✅ **全球CDN**：快速访问速度
- ✅ **Git集成**：自动部署GitHub/GitLab仓库
- ⚠️ **限制**：Serverless Functions有执行时间限制（免费版60秒）
- ⚠️ **文件系统**：只读（除了/tmp），知识库数据需要外部存储

## 前置要求

1. Vercel账号：https://vercel.com（可使用GitHub账号登录）
2. GitHub/GitLab/Bitbucket仓库
3. 项目代码已推送到仓库

## 部署步骤

### 方法1：通过Vercel网站部署（推荐）

1. **登录Vercel**
   - 访问 https://vercel.com
   - 使用GitHub账号登录

2. **导入项目**
   - 点击 "Add New..." → "Project"
   - 选择你的GitHub仓库
   - 点击 "Import"

3. **配置项目**
   - Framework Preset: 选择 "Other" 或 "Python"
   - Root Directory: `./`（默认）
   - Build Command: 留空（Vercel会自动检测）
   - Output Directory: 留空
   - Install Command: `pip install -r requirements.txt`

4. **环境变量**（可选）
   - `FLASK_ENV`: `production`
   - `PYTHONUTF8`: `1`

5. **部署**
   - 点击 "Deploy"
   - 等待构建完成（约2-5分钟）

6. **获得域名**
   - 部署完成后会获得一个URL：`https://your-project.vercel.app`
   - 可以在项目设置中配置自定义域名

### 方法2：使用Vercel CLI部署

1. **安装Vercel CLI**
```bash
npm i -g vercel
```

2. **登录**
```bash
vercel login
```

3. **部署**
```bash
cd E:\text_continuation_agent
vercel
```

4. **生产环境部署**
```bash
vercel --prod
```

## 项目结构要求

确保项目结构如下：
```
text_continuation_agent/
├── api/
│   └── index.py          # Vercel Serverless Function入口
├── static/               # 前端静态文件
│   ├── index.html
│   ├── style.css
│   └── app.js
├── app.py                # Flask应用
├── vercel.json           # Vercel配置文件
├── requirements.txt      # Python依赖
└── ...                   # 其他文件
```

## 重要配置说明

### 1. vercel.json配置

已创建的`vercel.json`包含：
- API路由：所有`/api/*`请求路由到`api/index.py`
- 静态文件：`/static/*`直接提供静态文件
- 首页：其他请求返回`index.html`

### 2. 执行时间限制

免费版Vercel Functions有60秒执行时间限制。如果续写任务较长，可能需要：
- 升级到Pro版本（20秒→300秒）
- 优化代码减少执行时间
- 使用异步处理

### 3. 文件系统限制

Vercel的文件系统是只读的（除了`/tmp`），这意味着：
- ❌ 知识库缓存文件（`faiss_kb_cache.pkl`）无法持久化
- ✅ 可以考虑使用外部存储（如Vercel KV、MongoDB、PostgreSQL）

## 数据持久化方案

### 方案1：使用Vercel KV（推荐）

1. 在Vercel项目设置中启用KV存储
2. 安装依赖：
```bash
pip install vercel-kv
```

3. 修改代码使用KV存储知识库数据

### 方案2：使用外部数据库

- MongoDB Atlas（免费版）
- PostgreSQL（Supabase免费版）
- Redis（Upstash免费版）

### 方案3：使用API调用（当前方案）

当前设计是用户在前端输入API密钥，不存储到服务器，所以知识库是临时的。

## 本地测试Vercel部署

使用Vercel CLI在本地测试：

```bash
# 安装CLI
npm i -g vercel

# 在项目目录运行
vercel dev
```

这会在本地启动一个模拟Vercel环境的服务器。

## 环境变量配置

在Vercel项目设置中添加环境变量：

1. 进入项目 → Settings → Environment Variables
2. 添加变量：
   - `FLASK_ENV`: `production`
   - `PYTHONUTF8`: `1`

## 自定义域名

1. 在项目设置 → Domains
2. 添加你的域名
3. 按照提示配置DNS记录
4. Vercel会自动配置HTTPS

## 性能优化

### 1. 启用边缘缓存

在`vercel.json`中添加：
```json
{
  "headers": [
    {
      "source": "/static/(.*)",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "public, max-age=31536000, immutable"
        }
      ]
    }
  ]
}
```

### 2. 优化Python包大小

创建`.vercelignore`文件排除不必要的文件：
```
__pycache__/
*.pyc
.venv/
*.pkl
bert-base-chinese/
.git/
```

### 3. 使用CDN加速

Vercel自动使用全球CDN，静态文件会自动缓存。

## 监控和日志

1. **实时日志**
   - 在Vercel Dashboard → 项目 → Functions → 查看日志

2. **分析**
   - Vercel Dashboard提供访问统计和性能分析

3. **错误追踪**
   - 在函数中添加错误日志
   - 使用Sentry等错误追踪服务

## 常见问题

### Q: 部署失败，提示找不到模块？
A: 确保`requirements.txt`包含所有依赖，特别是`flask`和`flask-cors`。

### Q: API请求超时？
A: 免费版有60秒限制。考虑优化代码或升级到Pro版本。

### Q: 静态文件404？
A: 检查`vercel.json`中的路由配置，确保静态文件路径正确。

### Q: 知识库数据丢失？
A: Vercel的文件系统是临时的。需要使用外部存储服务。

### Q: CORS错误？
A: 确保`app.py`中已启用`CORS(app)`。

## 部署检查清单

- [x] 创建了`vercel.json`配置文件
- [x] 创建了`api/index.py`入口文件
- [x] 更新了前端API基础URL为相对路径
- [x] 确保`requirements.txt`包含所有依赖
- [ ] 推送到GitHub仓库
- [ ] 在Vercel导入项目
- [ ] 配置环境变量
- [ ] 部署并测试

## 后续优化

1. **添加数据库支持**：使用MongoDB或PostgreSQL存储知识库
2. **用户认证**：添加用户登录系统
3. **API限流**：防止滥用
4. **监控告警**：设置错误告警
5. **性能优化**：减少冷启动时间

## 快速开始

```bash
# 1. 确保代码已推送到GitHub
git add .
git commit -m "准备Vercel部署"
git push

# 2. 访问Vercel网站导入项目
# https://vercel.com/new

# 3. 配置并部署
# 按照上面的步骤操作

# 4. 获得URL
# https://your-project.vercel.app
```

## 支持

如有问题，查看：
- Vercel文档：https://vercel.com/docs
- Vercel Python运行时：https://vercel.com/docs/concepts/functions/serverless-functions/runtimes/python

