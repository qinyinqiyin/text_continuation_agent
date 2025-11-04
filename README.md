# 文本续写助手

基于RAG（检索增强生成）的智能文本续写工具，支持多种风格续写和知识库管理。

## 功能特性

- 📝 **多风格续写**：支持奇幻、古风、科幻、玄幻、悬疑5种风格
- 🧠 **RAG增强**：基于FAISS向量数据库的知识库检索
- 🔧 **MCP工具集成**：文件系统和文本分析工具
- 🌐 **Web界面**：现代化的Flask + 前端架构
- ☁️ **Vercel部署**：一键部署到Vercel平台

## 技术栈

- **后端**：Flask + Python
- **前端**：HTML + CSS + JavaScript
- **AI模型**：阿里云DashScope API（通义千问）
- **向量数据库**：FAISS
- **嵌入模型**：BERT-base-chinese

## 快速开始

### 1. 环境要求

- Python 3.9+
- Conda（推荐）或虚拟环境

### 2. 安装依赖

```bash
conda activate myenv  # 或创建新环境
pip install -r requirements.txt
```

### 3. 下载模型文件

由于GitHub文件大小限制，BERT模型文件需要单独下载：

```bash
# 方法1：使用Hugging Face
git lfs install
git clone https://huggingface.co/bert-base-chinese bert-base-chinese

# 方法2：手动下载
# 访问 https://huggingface.co/bert-base-chinese
# 下载 pytorch_model.bin 到 bert-base-chinese/ 目录
```

需要的文件：
- `bert-base-chinese/pytorch_model.bin` (约392MB)
- `bert-base-chinese/config.json`
- `bert-base-chinese/vocab.txt`

### 4. 运行项目

**本地开发：**
```bash
python app.py
```

访问：http://localhost:5000

**使用Streamlit（旧版本）：**
```bash
streamlit run main.py
```

## 部署到Vercel

1. **推送代码到GitHub**
```bash
git add .
git commit -m "准备部署"
git push origin main
```

2. **在Vercel导入项目**
   - 访问 https://vercel.com
   - 连接GitHub仓库
   - 自动部署

3. **配置环境变量**（可选）
   - `FLASK_ENV`: `production`
   - `PYTHONUTF8`: `1`

详细部署说明请查看 [VERCEL_DEPLOY.md](VERCEL_DEPLOY.md)

## 项目结构

```
text_continuation_agent/
├── api/
│   └── index.py              # Vercel Serverless Function入口
├── static/                   # 前端文件
│   ├── index.html
│   ├── style.css
│   └── app.js
├── agent.py                  # Agent核心逻辑
├── app.py                    # Flask应用（主应用）
├── knowledge_base.py         # FAISS知识库
├── models.py                 # AI模型接口
├── strategies.py             # 续写策略
├── mcp_tools.py             # MCP工具集成
└── requirements.txt          # Python依赖
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

### MCP工具

- **文件系统工具**：批量导入、备份/恢复知识库
- **文本分析工具**：质量评分、风格检测、连贯性检查

详细使用说明请查看 [MCP_TOOLS_README.md](MCP_TOOLS_README.md)

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

### MCP工具
```
GET  /api/mcp/tools              # 列出工具
POST /api/mcp/tools/:name        # 执行工具
POST /api/mcp/analyze            # 文本分析
```

## 注意事项

1. **API密钥**：需要阿里云DashScope API密钥，用户在前端输入，不会存储到服务器
2. **知识库数据**：在Vercel部署时，知识库数据不会持久化（Serverless环境限制）
3. **模型文件**：BERT模型文件较大，需要单独下载或使用Git LFS

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！

## 更新日志

### v2.0.0
- ✅ 迁移到Flask + 前端架构
- ✅ 添加Vercel部署支持
- ✅ 集成MCP工具框架
- ✅ 优化用户界面

### v1.0.0
- ✅ 基础文本续写功能
- ✅ Streamlit界面
- ✅ RAG知识库检索
