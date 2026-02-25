# 文本续写助手

基于RAG（检索增强生成）的智能文本续写工具，支持多种风格续写和知识库管理。

## 功能特性

- 📝 **多风格续写**：支持奇幻、古风、科幻、玄幻、悬疑5种风格
- 🧠 **RAG增强**：基于FAISS向量数据库的知识库检索
- 🔧 **Function Call 工具**：文件系统和文本分析工具
- 🌐 **Web界面**：现代化的 FastAPI + 前端架构
- ☁️ **Vercel部署**：一键部署到Vercel平台

## 技术栈

- **后端**：FastAPI + LangChain（接收请求、返回 JSON）
- **前端**：HTML + CSS + JavaScript
- **AI 流程**：LangChain LCEL / RAG / Agent → 阿里云 DashScope（通义千问）
- **向量数据库**：FAISS
- **嵌入模型**：通义 embedding（text-embedding-v2，1536维）

## 快速开始

### 1. 环境要求

- Python 3.9+
- Conda（推荐）或虚拟环境

### 2. 安装依赖

```bash
conda activate myenv  # 或创建新环境
pip install -r requirements.txt
```

### 3. 配置 API 密钥

在项目根目录创建 `.env` 或设置环境变量：

```bash
cp .env.example .env
# 编辑 .env，填入 DASHSCOPE_API_KEY=sk-xxx
```

密钥从 [阿里云 DashScope 控制台](https://dashscope.console.aliyun.com/) 获取。

### 4. 运行项目

**推荐：FastAPI**
```bash
python main.py
```

访问：http://localhost:8000

**或使用 uvicorn：**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 部署选项

### 选项1: Vercel（推荐用于静态/轻量应用）

**优点**：快速部署，全球CDN，自动HTTPS  
**缺点**：构建时内存限制严格，不适合大型依赖

详细部署说明请查看项目文档

### 选项2: Railway（推荐用于需要向量检索的应用）⭐

**优点**：
- ✅ 构建时内存充足，不会OOM
- ✅ 支持安装PyTorch等大型依赖
- ✅ 自动部署，配置简单
- ✅ 每月$5免费额度

**快速部署**：
1. 访问 https://railway.app
2. 使用GitHub账号登录
3. 创建新项目，选择你的仓库
4. Railway自动检测Python项目并部署
5. 配置环境变量：`DASHSCOPE_API_KEY`（续写 + 嵌入共用）

### 选项3: Render

**优点**：免费PostgreSQL数据库，文档完善  
**缺点**：免费服务有冷启动（15分钟不活跃会休眠）

### 其他平台

支持部署到 Render、Vercel 等平台

**推荐**：
- 🥇 **Railway** - 最适合需要向量检索功能的项目
- 🥈 **Render** - 适合需要数据库的项目
- 🥉 **Google Cloud Run** - 适合生产环境

## 项目结构

```
text_continuation_agent/
├── main.py              # FastAPI 入口、RAGAgent、全部 API 路由
├── config.py            # DASHSCOPE_API_KEY、logger
├── base_classes.py      # BaseModel、BaseStrategy
├── embedding.py         # 通义 text-embedding-v2
├── langchain_llm.py     # LangChain Tongyi
├── strategies.py        # 5 种续写策略
├── knowledge_base.py    # FAISS 知识库
├── tools.py             # StoryTools（冲突检测、状态管理）
├── function_call.py     # Function Call 工具
├── eval_embedding.py    # 嵌入模型评估（可选）
├── api/index.py         # Vercel 入口
├── static/              # 前端
├── 函数手册与路径图.md
└── 技术文档.md
```

## 使用说明

### 文本续写

1. 输入阿里云DashScope API密钥
2. 选择续写风格
3. 输入前文内容
4. 设置续写参数（长度、创造性等）
5. 点击"开始续写"

### 知识库管理

- **添加设定**：手动添加角色设定、世界观设定等
- **上传文章**：批量上传TXT文件，自动分段
- **RAG检索**：续写时自动检索相关知识库内容

### Function Call 工具

- **文件系统工具**：批量导入、备份/恢复知识库
- **文本分析工具**：质量评分、风格检测、连贯性检查

## API接口

### 文本续写
```
POST /api/continuation
```

### 知识库管理
```
GET    /api/knowledge-base/settings      # 获取所有设定
POST   /api/knowledge-base/settings      # 添加设定
DELETE /api/knowledge-base/settings/:id  # 删除设定
POST   /api/knowledge-base/upload       # 上传文章
```

### Function Call 工具
```
GET  /api/tools                   # 列出工具
POST /api/tools/:name             # 执行工具
POST /api/tools/analyze           # 文本分析
```

## 注意事项

1. **API 密钥**：在 `config` 或 `.env` 中配置 `DASHSCOPE_API_KEY`，用于续写和嵌入
3. **知识库数据**：Serverless 环境下知识库不持久化

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！

## 更新日志

### v2.1.0
- ✅ Flask → LangChain LCEL / RAG → DashScope 流程
- ✅ 嵌入模型改用 HuggingFace API（acge_text_embedding，MTEB 中文榜第一）
- ✅ 无 HF Token 时自动回退到本地 BERT

### v2.0.0
- ✅ 迁移到Flask + 前端架构
- ✅ 添加Vercel部署支持
- ✅ 集成 Function Call 工具框架
- ✅ 优化用户界面

### v1.0.0
- ✅ 基础文本续写功能
- ✅ Streamlit界面
- ✅ RAG知识库检索
