"""
Flask后端API服务器
提供文本续写、知识库管理、MCP工具等API接口
"""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import json
from config import logger
from models import APIModel
from strategies import (
    FantasyStrategy, AncientStyleStrategy, SciFiStrategy,
    EasternFantasyStyleStrategy, SuspenseStrategy
)
from knowledge_base import FAISSKnowledgeBase
from agent import RAGTextContinuationAgent
from mcp_tools import create_mcp_registry

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)  # 允许跨域请求

# 全局状态管理（在实际生产环境中应使用Redis或数据库）
# 延迟加载knowledge_base以避免启动时加载大型模型导致OOM
_knowledge_base = None
agent_cache = {}  # 缓存Agent实例
mcp_registry = create_mcp_registry()

def get_knowledge_base():
    """延迟加载知识库，避免启动时内存不足"""
    global _knowledge_base
    if _knowledge_base is None:
        try:
            # 优先尝试使用本地模型（如果有依赖和模型文件）
            # 如果没有本地模型，fallback到API嵌入服务
            api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("HF_API_KEY")
            api_type = os.getenv("EMBEDDING_API_TYPE", "dashscope")
            
            # 检查是否有本地模型文件
            model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bert-base-chinese")
            has_local_model = os.path.exists(model_dir) and os.path.exists(
                os.path.join(model_dir, "pytorch_model.bin")
            )
            
            if has_local_model:
                # 使用本地模型
                _knowledge_base = FAISSKnowledgeBase(
                    use_api=False,  # 使用本地模型
                    model_name="bert-base-chinese"
                )
                logger.info("使用本地BERT模型进行向量检索")
            elif api_key:
                # Fallback到API嵌入服务
                _knowledge_base = FAISSKnowledgeBase(
                    use_api=True,
                    api_type=api_type,
                    api_key=api_key
                )
                logger.info(f"使用API嵌入服务: {api_type}")
            else:
                # 既没有本地模型也没有API密钥，使用简化模式
                logger.warning("未找到本地模型且未配置API密钥，将使用简化模式")
                _knowledge_base = SimpleKnowledgeBase()
        except (ImportError, FileNotFoundError, Exception) as e:
            # 如果初始化失败，fallback到简化模式
            logger.warning(f"知识库初始化失败: {str(e)}，将使用简化模式")
            _knowledge_base = SimpleKnowledgeBase()
    return _knowledge_base


class SimpleKnowledgeBase:
    """简化的知识库实现，用于缺少依赖时"""
    def __init__(self):
        self.documents = []
        self.metadatas = []
        logger.info("使用简化知识库模式（无向量检索功能）")
    
    def get_all_settings(self):
        return [(doc, meta) for doc, meta in zip(self.documents, self.metadatas)]
    
    def add_setting(self, setting_type: str, content: str):
        self.documents.append(content)
        self.metadatas.append({"type": setting_type})
        return f"已添加设定：{setting_type}"
    
    def delete_setting(self, setting_id: int):
        if 0 <= setting_id < len(self.documents):
            self.documents.pop(setting_id)
            self.metadatas.pop(setting_id)
            return True
        return False
    
    def clear_all_settings(self):
        self.documents.clear()
        self.metadatas.clear()
        return "已清空所有设定"
    
    def search(self, query: str, top_k: int = 3):
        # 简化实现：只返回文本匹配的结果
        results = []
        query_lower = query.lower()
        for doc, meta in zip(self.documents, self.metadatas):
            if query_lower in doc.lower():
                results.append((doc, meta))
        return results[:top_k]
    
    def search_relevant_settings(self, query: str, top_n: int = 3) -> list[str]:
        """搜索相关设定（简化版本，使用文本匹配）"""
        if not self.documents:
            return []
        query_lower = query.lower()
        relevant = []
        for doc in self.documents:
            if query_lower in doc.lower():
                relevant.append(doc)
                if len(relevant) >= top_n:
                    break
        return relevant


class StrategyFactory:
    @staticmethod
    def get_strategy(style: str):
        strategy_map = {
            "fantasy": FantasyStrategy,
            "ancient": AncientStyleStrategy,
            "sci-fi": SciFiStrategy,
            "EasternFantasy": EasternFantasyStyleStrategy,
            "Suspense": SuspenseStrategy
        }
        if style not in strategy_map:
            raise ValueError(f"不支持的风格：{style}")
        return strategy_map[style]()


def get_or_create_agent(api_key: str, style: str):
    """获取或创建Agent实例"""
    cache_key = f"{api_key[:10]}_{style}"
    if cache_key not in agent_cache:
        model = APIModel(api_key=api_key)
        strategy = StrategyFactory.get_strategy(style)
        agent = RAGTextContinuationAgent(model, strategy, get_knowledge_base())
        agent_cache[cache_key] = agent
    return agent_cache[cache_key]


# ==================== 静态文件服务 ====================

@app.route('/')
def index():
    """返回前端首页"""
    return send_from_directory('static', 'index.html')


# ==================== 文本续写API ====================

@app.route('/api/continuation', methods=['POST'])
def continuation():
    """文本续写接口"""
    try:
        data = request.json
        api_key = data.get('api_key')
        style = data.get('style', 'fantasy')
        context = data.get('context', '')
        requirements = data.get('requirements', '')
        max_length = data.get('max_length', 300)
        temperature = data.get('temperature', 0.6)
        use_rag = data.get('use_rag', True)
        
        if not api_key or not context.strip():
            return jsonify({"success": False, "error": "请完善API密钥和前文内容"}), 400
        
        # 获取或创建Agent
        agent = get_or_create_agent(api_key, style)
        
        input_data = {
            "前文": context,
            "要求": requirements
        }
        
        if use_rag:
            result = agent.run_with_rag(
                input_data,
                max_new_tokens=max_length,
                temperature=temperature
            )
        else:
            result = agent.run(
                input_data,
                max_new_tokens=max_length,
                temperature=temperature
            )
        
        return jsonify({
            "success": True,
            "result": result
        })
    except Exception as e:
        logger.error(f"续写失败: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== 知识库管理API ====================

@app.route('/api/knowledge-base/settings', methods=['GET'])
def get_settings():
    """获取所有设定"""
    try:
        all_settings = get_knowledge_base().get_all_settings()
        settings_list = []
        for idx, (doc, meta) in enumerate(all_settings):
            settings_list.append({
                "id": idx,
                "type": meta.get("type", "未知"),
                "content": doc
            })
        return jsonify({"success": True, "settings": settings_list})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/knowledge-base/settings', methods=['POST'])
def add_setting():
    """添加设定"""
    try:
        data = request.json
        setting_type = data.get('type')
        content = data.get('content')
        
        if not setting_type or not content:
            return jsonify({"success": False, "error": "设定类型和内容不能为空"}), 400
        
        msg = get_knowledge_base().add_setting(setting_type, content)
        return jsonify({"success": True, "message": msg})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/knowledge-base/settings/<int:setting_id>', methods=['DELETE'])
def delete_setting(setting_id):
    """删除设定"""
    try:
        success = get_knowledge_base().delete_setting(setting_id)
        if success:
            return jsonify({"success": True, "message": "删除成功"})
        else:
            return jsonify({"success": False, "error": "删除失败"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/knowledge-base/clear', methods=['POST'])
def clear_settings():
    """清空所有设定"""
    try:
        msg = get_knowledge_base().clear_all_settings()
        agent_cache.clear()  # 清空Agent缓存
        return jsonify({"success": True, "message": msg})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/knowledge-base/stats', methods=['GET'])
def get_kb_stats():
    """获取知识库统计信息"""
    try:
        all_settings = get_knowledge_base().get_all_settings()
        type_counts = {}
        for _, meta in all_settings:
            setting_type = meta.get("type", "未知")
            type_counts[setting_type] = type_counts.get(setting_type, 0) + 1
        
        return jsonify({
            "success": True,
            "total_count": len(all_settings),
            "type_counts": type_counts
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/knowledge-base/upload', methods=['POST'])
def upload_article():
    """上传文章文件"""
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "没有上传文件"}), 400
        
        file = request.files['file']
        chunk_size = int(request.form.get('chunk_size', 1000))
        overlap_size = int(request.form.get('overlap_size', 200))
        
        if file.filename == '':
            return jsonify({"success": False, "error": "文件名为空"}), 400
        
        # 读取文件内容
        file_content = file.read().decode('utf-8').strip()
        
        # 处理文件内容（改进的分段逻辑）
        segments = []
        
        # 如果文件内容小于chunk_size，也尝试分段（避免单一大段落）
        # 首先尝试按双换行分段
        paragraphs = [p.strip() for p in file_content.split('\n\n') if p.strip()]
        
        if not paragraphs:
            # 如果没有双换行，尝试按单换行分段
            paragraphs = [p.strip() for p in file_content.split('\n') if p.strip()]
        
        if not paragraphs:
            # 如果还是没有，尝试按句号分段
            import re
            sentences = re.split(r'[。！？\n]', file_content)
            paragraphs = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
        
        # 分段处理
        current_chunk = ""
        for para in paragraphs:
            para_text = para.strip()
            if not para_text:
                continue
            
            # 如果当前段落加上新段落超过chunk_size，保存当前块
            if current_chunk and len(current_chunk) + len(para_text) + 2 > chunk_size:
                if current_chunk.strip():
                    segments.append(current_chunk.strip())
                current_chunk = para_text
            else:
                # 如果单个段落就超过chunk_size，需要进一步切分
                if len(para_text) > chunk_size:
                    # 先保存当前块
                    if current_chunk.strip():
                        segments.append(current_chunk.strip())
                        current_chunk = ""
                    
                    # 切分超长段落
                    import re
                    # 尝试按句号切分
                    sentences = re.split(r'[。！？]', para_text)
                    temp_chunk = ""
                    for sent in sentences:
                        sent = sent.strip()
                        if not sent:
                            continue
                        if len(temp_chunk) + len(sent) + 1 > chunk_size:
                            if temp_chunk.strip():
                                segments.append(temp_chunk.strip())
                            temp_chunk = sent
                        else:
                            temp_chunk += sent + "。"
                    if temp_chunk.strip():
                        current_chunk = temp_chunk.strip()
                else:
                    # 正常添加到当前块
                    if current_chunk:
                        current_chunk += "\n\n" + para_text
                    else:
                        current_chunk = para_text
        
        # 保存最后一个块
        if current_chunk.strip():
            segments.append(current_chunk.strip())
        
        # 如果没有分到任何段落，使用整个文件内容
        if not segments:
            segments.append(file_content)
        
        # 添加到知识库
        success_count = 0
        for i, seg in enumerate(segments):
            if seg.strip() and len(seg.strip()) > 50:
                get_knowledge_base().add_setting(
                    "已有文章", f"[段落 {i+1}/{len(segments)}]\n{seg}"
                )
                success_count += 1
        
        return jsonify({
            "success": True,
            "message": f"文章已成功添加！共分割为 {success_count} 个段落",
            "segments_count": success_count
        })
    except Exception as e:
        logger.error(f"上传文章失败: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== MCP工具API ====================

@app.route('/api/mcp/tools', methods=['GET'])
def list_mcp_tools():
    """列出所有MCP工具"""
    try:
        tools = mcp_registry.list_tools()
        return jsonify({"success": True, "tools": tools})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/mcp/tools/<tool_name>', methods=['POST'])
def execute_mcp_tool(tool_name):
    """执行MCP工具"""
    try:
        data = request.json
        result = mcp_registry.execute_tool(tool_name, data)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/mcp/analyze', methods=['POST'])
def analyze_text():
    """文本分析接口（便捷方法）"""
    try:
        data = request.json
        text = data.get('text')
        reference_text = data.get('reference_text', '')
        style = data.get('style')
        api_key = data.get('api_key')
        
        if not text:
            return jsonify({"success": False, "error": "文本不能为空"}), 400
        
        if api_key and style:
            agent = get_or_create_agent(api_key, style)
            results = agent.analyze_text_quality(text, reference_text, style)
        else:
            # 直接使用MCP工具
            results = {}
            quality_result = mcp_registry.execute_tool("text_analysis", {
                "action": "quality_score",
                "text": text
            })
            if quality_result.get("success"):
                results["quality"] = quality_result["result"]
            
            if style:
                style_result = mcp_registry.execute_tool("text_analysis", {
                    "action": "style_detection",
                    "text": text,
                    "style": style
                })
                if style_result.get("success"):
                    results["style"] = style_result["result"]
            
            if reference_text:
                coherence_result = mcp_registry.execute_tool("text_analysis", {
                    "action": "coherence_check",
                    "text": text,
                    "reference_text": reference_text
                })
                if coherence_result.get("success"):
                    results["coherence"] = coherence_result["result"]
        
        return jsonify({"success": True, "results": results})
    except Exception as e:
        logger.error(f"文本分析失败: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== 健康检查 ====================

@app.route('/api/health', methods=['GET'])
def health():
    """健康检查接口"""
    return jsonify({"status": "ok", "message": "服务运行正常"})


if __name__ == '__main__':
    # 确保static目录存在
    os.makedirs('static', exist_ok=True)
    
    # 生产环境配置
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    
    app.run(host='0.0.0.0', port=port, debug=debug)

