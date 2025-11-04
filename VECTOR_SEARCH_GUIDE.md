# 向量检索功能使用指南

本文档说明如何在Vercel上启用和使用向量检索功能。

## 方案对比

| 方案 | 优点 | 缺点 | 推荐度 |
|------|------|------|--------|
| **方案1: API嵌入服务** | ✅ 无需本地模型<br>✅ 构建速度快<br>✅ 内存占用小 | ⚠️ 需要API密钥<br>⚠️ 有API调用成本 | ⭐⭐⭐⭐⭐ |
| **方案2: 本地模型+优化** | ✅ 无需API费用<br>✅ 完全离线 | ❌ 构建时间慢<br>❌ 内存占用大<br>❌ 可能OOM | ⭐⭐ |
| **方案3: 外部向量数据库** | ✅ 高性能<br>✅ 可扩展 | ⚠️ 需要额外服务<br>⚠️ 成本较高 | ⭐⭐⭐⭐ |

---

## 方案1: 使用API嵌入服务（推荐）

这是**最适合Vercel的方案**，无需加载大型模型，避免构建时OOM。

### 1.1 使用DashScope（阿里云）嵌入API

#### 步骤1: 获取API密钥
1. 访问 https://dashscope.console.aliyun.com/
2. 注册并获取API密钥
3. 确保开通了"文本向量化"服务

#### 步骤2: 配置环境变量
在Vercel项目设置中添加环境变量：
- `DASHSCOPE_API_KEY`: 你的DashScope API密钥
- `EMBEDDING_API_TYPE`: `dashscope`（可选，默认值）

#### 步骤3: 更新requirements.txt
```txt
flask>=2.3.0
flask-cors>=4.0.0
gunicorn>=21.2.0
dashscope>=1.19.3
python-dotenv>=1.0.0
requests>=2.31.0
numpy>=1.24.0
# faiss-cpu可选，如果不安装会使用numpy进行向量检索
# faiss-cpu>=1.7.4
```

#### 步骤4: 代码已自动支持
代码已自动检测环境变量并使用API嵌入服务，无需修改代码。

### 1.2 使用OpenAI嵌入API

#### 步骤1: 获取API密钥
1. 访问 https://platform.openai.com/
2. 注册并获取API密钥

#### 步骤2: 配置环境变量
- `OPENAI_API_KEY`: 你的OpenAI API密钥
- `EMBEDDING_API_TYPE`: `openai`

#### 步骤3: 更新requirements.txt
```txt
openai>=1.0.0
```

### 1.3 使用Hugging Face Inference API

#### 步骤1: 获取API Token
1. 访问 https://huggingface.co/
2. 创建账号并获取Access Token

#### 步骤2: 配置环境变量
- `HF_API_KEY`: 你的Hugging Face Token
- `EMBEDDING_API_TYPE`: `huggingface`

---

## 方案2: 使用本地模型（不推荐用于Vercel）

如果你的项目不在Vercel上，或者想要完全离线运行，可以使用本地模型。

### 步骤1: 启用依赖
取消注释 `requirements.txt` 中的依赖：
```txt
torch>=2.0.0,<3.0.0
transformers>=4.30.0,<5.0.0
faiss-cpu>=1.7.4
numpy>=1.24.0
```

### 步骤2: 下载模型文件
```bash
# 使用Hugging Face
git lfs install
git clone https://huggingface.co/bert-base-chinese bert-base-chinese
```

### 步骤3: 修改代码
在 `app.py` 中修改 `get_knowledge_base()`:
```python
_knowledge_base = FAISSKnowledgeBase(
    use_api=False,  # 使用本地模型
    model_name="bert-base-chinese"
)
```

### ⚠️ 注意事项
- 本地模型需要约400MB空间
- 构建时可能遇到OOM错误
- 推荐用于本地开发或自有服务器

---

## 方案3: 使用外部向量数据库（高级）

对于大规模应用，可以使用专业的向量数据库服务。

### 3.1 Pinecone
```python
# 安装
pip install pinecone-client

# 使用
import pinecone
pinecone.init(api_key="your-api-key")
index = pinecone.Index("your-index-name")
```

### 3.2 Weaviate Cloud
```python
# 安装
pip install weaviate-client

# 使用
import weaviate
client = weaviate.Client("https://your-cluster.weaviate.network")
```

### 3.3 Qdrant
```python
# 安装
pip install qdrant-client

# 使用
from qdrant_client import QdrantClient
client = QdrantClient(url="https://your-cluster.qdrant.io")
```

---

## 性能优化建议

### 1. 缓存嵌入向量
避免重复计算相同文本的嵌入：
```python
# 在knowledge_base.py中已实现缓存机制
```

### 2. 批量处理
API调用支持批量处理，减少API调用次数：
```python
# embedding_api.py中已实现批量处理
```

### 3. 使用FAISS加速
如果安装了faiss-cpu，向量检索会更快：
```bash
pip install faiss-cpu
```

---

## 成本估算

### DashScope（阿里云）
- 文本向量化API：约 ¥0.001/千次调用
- 适合中小规模应用

### OpenAI
- text-embedding-ada-002: $0.0001/1K tokens
- 适合英文应用

### Hugging Face
- Inference API：免费额度有限
- 适合开发测试

---

## 故障排查

### 问题1: API调用失败
**症状**: 日志显示"API嵌入失败"
**解决**:
1. 检查API密钥是否正确
2. 检查API额度是否充足
3. 检查网络连接

### 问题2: 向量维度不匹配
**症状**: "编码维度异常"
**解决**:
1. 确保使用相同的嵌入模型
2. 清空缓存重新构建索引

### 问题3: 检索结果不准确
**症状**: 检索到的内容不相关
**解决**:
1. 检查文本预处理是否正确
2. 尝试调整top_n参数
3. 考虑使用更好的嵌入模型

---

## 示例代码

### 在Vercel上使用DashScope API
```python
# app.py会自动检测环境变量
# 只需设置环境变量即可：

# Vercel环境变量：
# DASHSCOPE_API_KEY=sk-xxxxx
# EMBEDDING_API_TYPE=dashscope
```

### 本地开发使用本地模型
```python
# 在app.py中修改
_knowledge_base = FAISSKnowledgeBase(
    use_api=False,
    model_name="bert-base-chinese"
)
```

---

## 总结

- **Vercel部署**: 推荐使用方案1（API嵌入服务）
- **本地开发**: 可以使用方案2（本地模型）
- **生产环境**: 考虑方案3（外部向量数据库）

选择最适合你场景的方案即可！

