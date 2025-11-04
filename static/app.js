// 全局状态
let continuationHistory = '';
let currentResult = '';
let currentApiKey = '';
let currentStyle = 'fantasy';

// API基础URL - 自动检测环境
// 开发环境使用localhost，生产环境使用相对路径
const API_BASE = window.location.hostname === 'localhost' 
    ? 'http://localhost:5000/api' 
    : '/api';

// ==================== 标签页切换 ====================

document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const tabName = btn.dataset.tab;
        switchTab(tabName);
    });
});

function switchTab(tabName) {
    // 更新标签按钮
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    
    // 更新内容
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById(tabName).classList.add('active');
    
    // 加载数据
    if (tabName === 'settings') {
        loadSettings();
    }
}

// 子标签切换
document.querySelectorAll('.sub-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const subtabName = btn.dataset.subtab;
        switchSubTab(subtabName);
    });
});

function switchSubTab(subtabName) {
    document.querySelectorAll('.sub-tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`[data-subtab="${subtabName}"]`).classList.add('active');
    
    document.querySelectorAll('.sub-tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById(subtabName).classList.add('active');
    
    if (subtabName === 'text-analysis') {
        updateAnalysisForm();
    }
}

// ==================== 文本续写 ====================

// 更新滑块显示值
document.getElementById('max-length').addEventListener('input', (e) => {
    document.getElementById('max-length-value').textContent = e.target.value;
});

document.getElementById('temperature').addEventListener('input', (e) => {
    document.getElementById('temperature-value').textContent = parseFloat(e.target.value).toFixed(1);
});

async function startContinuation() {
    const apiKey = document.getElementById('api-key').value;
    const style = document.getElementById('style').value;
    const context = document.getElementById('context').value;
    const requirements = document.getElementById('requirements').value;
    const maxLength = parseInt(document.getElementById('max-length').value);
    const temperature = parseFloat(document.getElementById('temperature').value);
    const useRag = document.getElementById('use-rag').checked;
    
    if (!apiKey || !context.trim()) {
        alert('请完善API密钥和前文内容');
        return;
    }
    
    currentApiKey = apiKey;
    currentStyle = style;
    
    // 显示加载
    document.getElementById('loading').style.display = 'block';
    document.getElementById('continuation-result').style.display = 'none';
    
    try {
        const response = await fetch(`${API_BASE}/continuation`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                api_key: apiKey,
                style: style,
                context: context,
                requirements: requirements,
                max_length: maxLength,
                temperature: temperature,
                use_rag: useRag
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            currentResult = data.result;
            document.getElementById('result-content').textContent = data.result;
            document.getElementById('continuation-result').style.display = 'block';
        } else {
            alert('续写失败：' + data.error);
        }
    } catch (error) {
        alert('请求失败：' + error.message);
    } finally {
        document.getElementById('loading').style.display = 'none';
    }
}

function mergeResult() {
    if (!currentResult.trim()) {
        alert('没有可合并的续写结果');
        return;
    }
    
    const contextTextarea = document.getElementById('context');
    continuationHistory = continuationHistory + '\n' + currentResult;
    contextTextarea.value = continuationHistory;
    currentResult = '';
    document.getElementById('continuation-result').style.display = 'none';
    alert('合并成功！');
}

function downloadText() {
    const fullText = continuationHistory + (currentResult ? '\n' + currentResult : '');
    if (!fullText.trim()) {
        alert('暂无内容可下载');
        return;
    }
    
    const blob = new Blob([fullText], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'full_story.txt';
    a.click();
    URL.revokeObjectURL(url);
}

// ==================== 知识库管理 ====================

async function loadSettings() {
    try {
        const response = await fetch(`${API_BASE}/knowledge-base/settings`);
        const data = await response.json();
        
        if (data.success) {
            displaySettings(data.settings);
            updateKBStats(data.settings);
        }
    } catch (error) {
        console.error('加载设定失败：', error);
    }
}

async function loadKBStats() {
    try {
        const response = await fetch(`${API_BASE}/knowledge-base/stats`);
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('kb-total-count').textContent = data.total_count;
        }
    } catch (error) {
        console.error('加载统计失败：', error);
    }
}

function updateKBStats(settings) {
    document.getElementById('kb-total-count').textContent = settings.length;
}

function displaySettings(settings) {
    const container = document.getElementById('settings-list');
    
    if (settings.length === 0) {
        container.innerHTML = '<p class="empty-message">尚未添加任何设定</p>';
        return;
    }
    
    // 按类型分组
    const typeGroups = {};
    settings.forEach(setting => {
        const type = setting.type;
        if (!typeGroups[type]) {
            typeGroups[type] = [];
        }
        typeGroups[type].push(setting);
    });
    
    let html = '';
    for (const [type, items] of Object.entries(typeGroups)) {
        html += `<div class="setting-group">
            <h4>${type} (${items.length}条)</h4>`;
        
        items.forEach(item => {
            html += `<div class="setting-item">
                <div class="setting-header">
                    <span class="setting-type">${item.type}</span>
                    <button class="btn btn-danger" onclick="deleteSetting(${item.id})">删除</button>
                </div>
                <div class="setting-content">${escapeHtml(item.content.substring(0, 300))}${item.content.length > 300 ? '...' : ''}</div>
            </div>`;
        });
        
        html += '</div>';
    }
    
    container.innerHTML = html;
}

async function addSetting() {
    const type = document.getElementById('setting-type').value;
    const content = document.getElementById('setting-content').value;
    
    if (!content.trim()) {
        alert('请输入设定内容');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/knowledge-base/settings`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                type: type,
                content: content
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('添加成功！');
            document.getElementById('setting-content').value = '';
            loadSettings();
            loadKBStats();
        } else {
            alert('添加失败：' + data.error);
        }
    } catch (error) {
        alert('请求失败：' + error.message);
    }
}

async function deleteSetting(id) {
    if (!confirm('确定要删除这个设定吗？')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/knowledge-base/settings/${id}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('删除成功！');
            loadSettings();
            loadKBStats();
        } else {
            alert('删除失败：' + data.error);
        }
    } catch (error) {
        alert('请求失败：' + error.message);
    }
}

async function clearAllSettings() {
    if (!confirm('确定要清空所有设定吗？此操作不可恢复！')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/knowledge-base/clear`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('清空成功！');
            loadSettings();
            loadKBStats();
        } else {
            alert('清空失败：' + data.error);
        }
    } catch (error) {
        alert('请求失败：' + error.message);
    }
}

// ==================== 文件上传 ====================

let selectedFile = null;

function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
        selectedFile = file;
        const fileInfo = document.getElementById('file-info');
        fileInfo.innerHTML = `📄 文件名：${file.name} | 文件大小：${file.size} 字节`;
        fileInfo.style.display = 'block';
        document.getElementById('upload-btn').disabled = false;
    }
}

async function uploadArticle() {
    if (!selectedFile) {
        alert('请先选择文件');
        return;
    }
    
    const chunkSize = parseInt(document.getElementById('chunk-size').value);
    const overlapSize = parseInt(document.getElementById('overlap-size').value);
    
    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('chunk_size', chunkSize);
    formData.append('overlap_size', overlapSize);
    
    document.getElementById('upload-btn').disabled = true;
    document.getElementById('upload-btn').textContent = '上传中...';
    
    try {
        const response = await fetch(`${API_BASE}/knowledge-base/upload`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(`上传成功！共分割为 ${data.segments_count} 个段落`);
            selectedFile = null;
            document.getElementById('file-upload').value = '';
            document.getElementById('file-info').style.display = 'none';
            loadSettings();
            loadKBStats();
        } else {
            alert('上传失败：' + data.error);
        }
    } catch (error) {
        alert('请求失败：' + error.message);
    } finally {
        document.getElementById('upload-btn').disabled = false;
        document.getElementById('upload-btn').textContent = '✅ 添加文章到知识库';
    }
}

// ==================== MCP工具 ====================

function handleFsActionChange() {
    const action = document.getElementById('fs-action').value;
    const container = document.getElementById('fs-action-content');
    
    let html = '';
    
    if (action === 'import') {
        html = `
            <div class="form-group">
                <label>目录路径</label>
                <input type="text" id="import-path" placeholder="例如：E:/articles 或 ./articles">
            </div>
            <div class="form-group">
                <label>文件扩展名</label>
                <div>
                    <label><input type="checkbox" value=".txt" checked> .txt</label>
                    <label><input type="checkbox" value=".md"> .md</label>
                </div>
            </div>
            <button class="btn btn-primary" onclick="importDirectory()">🚀 开始导入</button>
        `;
    } else if (action === 'backup') {
        html = `
            <div class="form-group">
                <label>备份路径（留空使用默认名称）</label>
                <input type="text" id="backup-path" placeholder="例如：backup_kb_20241031.pkl">
            </div>
            <button class="btn btn-primary" onclick="backupKB()">💾 开始备份</button>
        `;
    } else if (action === 'restore') {
        html = `
            <div class="form-group">
                <label>备份文件路径</label>
                <input type="text" id="restore-path" placeholder="例如：backup_kb_20241031.pkl">
            </div>
            <button class="btn btn-danger" onclick="restoreKB()">🔄 恢复知识库</button>
        `;
    } else if (action === 'list') {
        html = `
            <div class="form-group">
                <label>目录路径</label>
                <input type="text" id="list-path" value=".">
            </div>
            <button class="btn btn-primary" onclick="listFiles()">📋 列出文件</button>
            <div id="file-list-result"></div>
        `;
    }
    
    container.innerHTML = html;
}

async function importDirectory() {
    const path = document.getElementById('import-path').value;
    const checkboxes = document.querySelectorAll('#fs-action-content input[type="checkbox"]:checked');
    const extensions = Array.from(checkboxes).map(cb => cb.value);
    
    if (!path) {
        alert('请输入目录路径');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/mcp/tools/filesystem`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                action: 'import_directory',
                source_path: path,
                file_extensions: extensions
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(`成功导入 ${data.result.imported_count} 个文件`);
        } else {
            alert('导入失败：' + data.error);
        }
    } catch (error) {
        alert('请求失败：' + error.message);
    }
}

async function backupKB() {
    const path = document.getElementById('backup-path').value;
    
    try {
        const response = await fetch(`${API_BASE}/mcp/tools/filesystem`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                action: 'backup',
                target_path: path || null
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('备份成功！');
            console.log(data.result);
        } else {
            alert('备份失败：' + data.error);
        }
    } catch (error) {
        alert('请求失败：' + error.message);
    }
}

async function restoreKB() {
    const path = document.getElementById('restore-path').value;
    
    if (!confirm('确定要恢复知识库吗？当前知识库将被覆盖！')) {
        return;
    }
    
    if (!path) {
        alert('请输入备份文件路径');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/mcp/tools/filesystem`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                action: 'restore',
                source_path: path
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('恢复成功！请刷新页面');
            location.reload();
        } else {
            alert('恢复失败：' + data.error);
        }
    } catch (error) {
        alert('请求失败：' + error.message);
    }
}

async function listFiles() {
    const path = document.getElementById('list-path').value;
    
    try {
        const response = await fetch(`${API_BASE}/mcp/tools/filesystem`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                action: 'list_files',
                source_path: path
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            const result = data.result;
            const container = document.getElementById('file-list-result');
            let html = `<p>找到 ${result.file_count} 个文件：</p><ul>`;
            result.files.forEach(file => {
                html += `<li>${file.name} (${file.size} 字节)</li>`;
            });
            html += '</ul>';
            container.innerHTML = html;
        } else {
            alert('列出文件失败：' + data.error);
        }
    } catch (error) {
        alert('请求失败：' + error.message);
    }
}

// ==================== 文本分析 ====================

function updateAnalysisForm() {
    const action = document.getElementById('analysis-action').value;
    const refContainer = document.getElementById('analysis-ref-container');
    const styleContainer = document.getElementById('analysis-style-container');
    
    refContainer.style.display = (action === 'coherence_check' || action === 'duplicate_detection') ? 'block' : 'none';
    styleContainer.style.display = (action === 'style_detection') ? 'block' : 'none';
}

document.getElementById('analysis-action').addEventListener('change', updateAnalysisForm);

async function analyzeText() {
    const action = document.getElementById('analysis-action').value;
    const text = document.getElementById('analysis-text').value;
    const refText = document.getElementById('analysis-ref').value;
    const style = document.getElementById('analysis-style').value;
    
    if (!text.trim()) {
        alert('请输入待分析文本');
        return;
    }
    
    const params = {
        action: action,
        text: text
    };
    
    if (refText && (action === 'coherence_check' || action === 'duplicate_detection')) {
        params.reference_text = refText;
    }
    
    if (style && action === 'style_detection') {
        params.style = style;
    }
    
    try {
        const response = await fetch(`${API_BASE}/mcp/tools/text_analysis`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(params)
        });
        
        const data = await response.json();
        
        if (data.success) {
            displayAnalysisResult(data.result);
        } else {
            alert('分析失败：' + data.error);
        }
    } catch (error) {
        alert('请求失败：' + error.message);
    }
}

function displayAnalysisResult(result) {
    const container = document.getElementById('analysis-result-content');
    container.innerHTML = `<pre>${JSON.stringify(result, null, 2)}</pre>`;
    document.getElementById('analysis-result').style.display = 'block';
}

// ==================== 工具函数 ====================

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==================== 初始化 ====================

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', () => {
    loadKBStats();
    handleFsActionChange();
    updateAnalysisForm();
});

