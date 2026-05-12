# StoryWriter 长篇助手

借鉴论文架构的多阶段长篇小说接写服务：**Outline → Planning → Writing**，结合向量知识库检索、LangChain 工具调用（本地 Markdown / 联网搜索）与 Web 前台。

## 功能概览

- **三阶段 Agent**：先做事件化纲要，再做下一书写单元规划，最后用工具辅助生成接续正文。
- **共享工具**：Outline / Planning / Writing 共用同一套工具（章节 Markdown、参考模板 Markdown、DuckDuckGo 检索）。
- **分阶段向量检索**：每个阶段根据自身上下文单独检索 Chroma，摘录写入该阶段系统提示。
- **已有正文**：不写入向量库；合并稿放在 `markdown/existing articles.md`，按正文中的 **`第N章`**（行首）切分，`query_article_chapter_markdown` 传入 **`1`**、**`第2章`** 等即可取对应章节。
- **设定类知识库**：角色、世界观、大纲等仍可写入 **Chroma** 供 RAG 使用；不提供「已有文章」类型条目。
- **Web 前台**：FastAPI 托管静态页——**故事续写**、**设定管理**。

## 技术栈

| 组件 | 说明 |
|------|------|
| 后端 | FastAPI、`deps` 生命周期、单例知识库与 Agent |
| LLM | LangChain Tongyi（纲要/规划）；ChatTongyi + `AgentExecutor`（三阶段带工具） |
| 向量库 | **Chroma** 持久化 + 通义 **text-embedding-v2** |
| 检索增强 | `rerank` 对向量命中结果二次排序 |
| 前端 | `static/`：HTML/CSS/原生 JS |

## 环境要求

- Python **3.9+**（建议 **conda**，例如环境名 `myenv`）
- 阿里云 **DashScope API Key**（续写与嵌入共用）

## 快速开始

### 1. 安装依赖

```bash
conda activate myenv   # 或你的虚拟环境
cd /path/to/text_continuation_agent_clone_tmp
pip install -r requirements.txt
```

若未激活环境直接使用系统 `python`，可能缺少 `chromadb` 等依赖；推荐始终在同一环境中安装与启动。

### 2. 配置环境变量

在项目根目录新建 **`.env`**（UTF-8），至少包含：

```bash
DASHSCOPE_API_KEY=sk-xxxx
PORT=8000
# 可选：Chroma 落盘路径（默认 ./chroma_kb_store）
# CHROMA_PERSIST_DIR=./chroma_kb_store
```

与 Markdown 相关的可选变量（不配则使用默认值）：

| 变量 | 默认含义 |
|------|----------|
| `EXISTING_ARTICLES_MD_PATH` | `{项目根}/markdown/existing articles.md` 合并正文 |
| `STORY_ARTICLE_MD_DIR` | `{项目根}/markdown/`（兼容按文件名读单篇 `.md`） |
| `STORY_TEMPLATE_MD_DIR` | `{项目根}/markdown/`（参考模板，如 `reference template.md`） |

### 3. 准备正文与模板（可选）

- 将整部既有正文写入 **`markdown/existing articles.md`**，章起始行使用 **`第1章`、`第2章`** 等格式。
- 参考文风可放入 **`markdown/reference template.md`**，工具中用模板文件名主干调用。

### 4. 启动服务

```bash
python main.py
# 或
uvicorn main:app --host 0.0.0.0 --port 8000
```

浏览器访问：**http://127.0.0.1:8000**（端口以 `PORT` 为准）。

自检：`GET /api/config/check` 可查看 API Key 是否读到、Markdown 路径解析结果等。

## 项目结构（核心文件）

```
.
├── main.py                 # FastAPI 入口、REST 路由
├── deps.py                 # lifespan、全局 KB / Agent 单例
├── config.py               # 环境变量、Markdown 路径、日志
├── rag_agent.py            # StoryWriter 管线：检索 + 三阶段 Agent
├── storywriter_agents.py   # 系统提示、共享上下文文案、共享工具说明
├── story_markdown_tools.py # 章节 / 模板 / DuckDuckGo 工具
├── langchain_llm.py        # Tongyi + ChatTongyi
├── knowledge_base.py       # ChromaKnowledgeBase（写入、检索；排除「已有文章」类型参与 RAG）
├── rerank.py               # DashScope rerank（若可用）
├── markdown/               # 默认 Markdown 根：`existing articles.md`、`reference template.md`
├── chroma_kb_store/        # Chroma 默认持久化目录（可改环境变量）
└── static/                 # 前端：index.html、app.js、style.css
```

## 使用说明

### 故事续写

1. 在「前文」粘贴接写起点，可填「本轮意图 / 约束」。
2. 调节生成长度与 temperature，点击「开始续写」。
3. 可展开查看 **Outline**、**Planning** 与最终正文；支持合并到前文、下载文本。

### 设定管理

- 手动添加或上传 **TXT** 到向量知识库（类型：文章大纲、角色设定、世界观设定等）。
- **不再**提供将「已有文章」整篇写入向量库；正文请用合并稿 + 工具按章读取。

### Agent 工具（模型侧）

- **`query_article_chapter_markdown`**：优先按章节号从 **`existing articles.md`** 切段；否则在 `STORY_ARTICLE_MD_DIR` 下按文件名查整文件。
- **`query_reference_template_markdown`**：在模板目录按主干名读取，如 **`reference template`**。
- **`web_search_story_assistance`**：依赖 **`duckduckgo-search`**（已列入 `requirements.txt`）。

## API 摘要

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/config/check` | 配置与 Markdown 路径预览 |
| POST | `/api/continuation` | 接写：`context`、`requirements`、`max_length`、`temperature` |
| GET | `/api/knowledge-base/settings` | 列出设定 |
| POST | `/api/knowledge-base/settings` | 添加设定（JSON：`type`、`content`） |
| DELETE | `/api/knowledge-base/settings/{id}` | 按序号删除 |
| POST | `/api/knowledge-base/upload` | 表单上传 TXT |
| POST | `/api/knowledge-base/clear` | 清空向量库 |

## 部署提示

云端部署时需持久化 **`CHROMA_PERSIST_DIR`** 对应目录，否则会话间知识库会丢失。**Vercel 等 Serverless** 不适合长驻 Chroma；更稳妥方式为 **Railway / Render / 自有 VPS / Docker + 挂载卷**。具体绑定域名与 HTTPS 按平台文档操作即可。

## 注意事项

1. **`DASHSCOPE_API_KEY`** 勿提交仓库；`.env` 已在 `.gitignore` 中。
2. DuckDuckGo 在大陆网络环境下可能不稳定，可按需替换为其它搜索工具适配层。
3. LangChain Community 中对 **Chroma** 的弃用告警仅为提示；后续可迁至 `langchain-chroma` 包。

## 许可证

MIT License

## 更新日志（摘要）

### 近期

- StoryWriter：**Outline → Planning → Writing**，三阶段 **ChatTongyi + 共享工具**，每阶段独立向量检索。
- 向量库：**FAISS → Chroma**；正文合并稿 **`markdown/existing articles.md`** + **按「第N章」切工具读**。
- 知识库类型移除「已有文章」入向量逻辑；前台移除「文件与备份」占位页。
- 依赖补充 **duckduckgo-search**。

### 更早版本

- 历史曾有过 Flask / Streamlit、FAISS、Function Call 文件系统占位等与当前主干不一致的实现，均已由当前仓库结构替代。

