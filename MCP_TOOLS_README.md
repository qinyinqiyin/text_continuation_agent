# MCP工具使用说明

## 概述

本项目已集成MCP（Model Context Protocol）工具框架，提供了标准化的工具调用接口，增强了文本续写功能。

## 已实现的MCP工具

### 1. 文件系统工具 (filesystem)

**功能：**
- 批量导入文章：从指定目录批量导入TXT文件
- 备份知识库：备份当前知识库到指定位置
- 恢复知识库：从备份文件恢复知识库
- 列出文件：列出指定目录中的文件

**使用场景：**
- 批量导入已有文章到知识库
- 定期备份知识库数据
- 在不同项目间迁移知识库

**示例：**
```python
from mcp_tools import create_mcp_registry

registry = create_mcp_registry()
tool = registry.get_tool("filesystem")

# 批量导入
result = tool.execute(
    action="import_directory",
    source_path="./articles",
    file_extensions=[".txt"]
)

# 备份知识库
result = tool.execute(
    action="backup",
    target_path="backup_20241031.pkl"
)
```

### 2. 文本分析工具 (text_analysis)

**功能：**
- 质量评分：评估文本的整体质量（长度、段落结构、句子多样性、词汇丰富度）
- 风格检测：检测文本的风格类型和匹配度
- 连贯性检查：检查文本与参考文本的连贯性
- 重复检测：检测文本中的重复内容
- 情感分析：分析文本的情感倾向

**使用场景：**
- 评估续写结果的质量
- 检查风格一致性
- 确保前后文连贯
- 避免重复内容

**示例：**
```python
from mcp_tools import create_mcp_registry

registry = create_mcp_registry()
tool = registry.get_tool("text_analysis")

# 质量评分
result = tool.execute(
    action="quality_score",
    text="你的文本内容..."
)

# 风格检测
result = tool.execute(
    action="style_detection",
    text="你的文本内容...",
    style="EasternFantasy"
)

# 连贯性检查
result = tool.execute(
    action="coherence_check",
    text="续写内容...",
    reference_text="前文内容..."
)
```

## 在Agent中使用MCP工具

### 方法1：直接调用MCP工具

```python
from agent import RAGTextContinuationAgent

agent = RAGTextContinuationAgent(model, strategy, knowledge_base)

# 调用MCP工具
result = agent.call_mcp_tool("text_analysis", {
    "action": "quality_score",
    "text": "你的文本..."
})
```

### 方法2：使用便捷分析方法

```python
# 分析文本质量（自动调用多个分析工具）
analysis_results = agent.analyze_text_quality(
    text="续写内容",
    reference_text="前文内容",
    style="EasternFantasy"
)

# 返回结果包含：
# - quality: 质量评分
# - style: 风格检测结果
# - coherence: 连贯性检查结果
# - duplicate: 重复检测结果
```

## 在Streamlit界面中使用

1. **打开MCP工具标签页**：在主界面点击"🔧 MCP工具"标签

2. **文件系统工具**：
   - 选择操作类型（批量导入、备份、恢复、列出文件）
   - 输入路径和相关参数
   - 点击执行按钮

3. **文本分析工具**：
   - 选择分析类型
   - 输入待分析文本
   - 如需要，输入参考文本或目标风格
   - 点击"开始分析"查看结果

4. **快速分析续写结果**：
   - 在文本分析标签页底部
   - 点击"分析当前续写结果"按钮
   - 自动分析当前续写结果的质量、风格、连贯性等

## 工具架构

```
MCPTool (基类)
├── get_schema() - 返回JSON Schema定义
├── execute() - 执行工具逻辑
└── validate_params() - 验证参数

MCPToolRegistry (注册表)
├── register() - 注册工具
├── get_tool() - 获取工具
├── list_tools() - 列出所有工具
└── execute_tool() - 执行工具（带验证和错误处理）
```

## 扩展新的MCP工具

要添加新的MCP工具，只需：

1. **创建工具类**：
```python
from mcp_tools import MCPTool

class MyNewTool(MCPTool):
    def __init__(self):
        super().__init__(
            name="my_tool",
            description="工具描述"
        )
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "参数1"}
            },
            "required": ["param1"]
        }
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        # 实现工具逻辑
        return {"result": "工具执行结果"}
```

2. **注册工具**：
```python
from mcp_tools import create_mcp_registry

registry = create_mcp_registry()
registry.register(MyNewTool())
```

## 注意事项

1. **文件编码**：所有文本文件应使用UTF-8编码
2. **路径格式**：Windows路径可以使用正斜杠或反斜杠
3. **备份恢复**：恢复知识库会覆盖当前数据，请谨慎操作
4. **性能考虑**：批量导入大量文件时可能需要较长时间

## 未来扩展方向

- [ ] 网络搜索工具（获取参考资料）
- [ ] 知识图谱工具（可视化角色关系）
- [ ] 版本管理工具（管理续写版本）
- [ ] 数据库工具（更好的数据管理）
- [ ] API集成工具（集成更多AI服务）

## 技术支持

如有问题或建议，请查看项目文档或提交Issue。

