// QQ聊天机器人管理页面前端逻辑

const API_BASE = '';
let ws = null;
let currentPage = 1;
let isPaused = false;
let messageCount = 0;

// ========== WebSocket ==========
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

    ws.onopen = () => console.log('WebSocket已连接');
    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleWebSocketMessage(msg);
    };
    ws.onclose = () => {
        console.log('WebSocket断开，5秒后重连...');
        setTimeout(connectWebSocket, 5000);
    };
    ws.onerror = (err) => console.error('WebSocket错误:', err);
}

function handleWebSocketMessage(msg) {
    if (msg.type === 'new_message') {
        addMessageToStream(msg.data);
    } else if (msg.type === 'bot_reply') {
        addMessageToStream({...msg.data, is_bot: true});
        messageCount++;
        document.getElementById('control-msg-count').textContent = messageCount;
        document.getElementById('control-last-reply').textContent = (msg.data.content || '').slice(0, 30);
    } else if (msg.type === 'status_update') {
        updateStatusDisplay(msg.data);
    }
}

// ========== 标签页切换 ==========
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('tab-btn')) {
        const tabId = e.target.dataset.tab;
        document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
        e.target.classList.add('active');
        document.getElementById(`tab-${tabId}`).classList.add('active');

        if (tabId === 'logs') loadLogs();
        if (tabId === 'memory') loadMemory();
    }
});

// ========== 实时消息流 ==========
function addMessageToStream(data) {
    const stream = document.getElementById('message-stream');
    const emptyTip = stream.querySelector('.empty-tip');
    if (emptyTip) emptyTip.remove();

    const div = document.createElement('div');
    div.className = `message-item ${data.is_bot ? 'bot' : ''}`;
    div.innerHTML = `
        <div class="msg-header">
            <span>${escapeHtml(data.sender || '未知用户')}</span>
            <span>${data.timestamp || new Date().toLocaleTimeString()}</span>
        </div>
        <div class="msg-content">${escapeHtml(data.content || '')}</div>
    `;
    stream.appendChild(div);
    stream.scrollTop = stream.scrollHeight;
}

// ========== 状态获取 ==========
async function fetchStatus() {
    try {
        const res = await fetch(`${API_BASE}/api/control/status`);
        const data = await res.json();
        updateStatusDisplay(data);
    } catch (e) {
        console.error('获取状态失败:', e);
    }
}

function updateStatusDisplay(data) {
    const indicator = document.getElementById('status-indicator');
    const statusText = document.getElementById('status-text');
    const windowStatus = document.getElementById('window-status');

    isPaused = data.paused;

    if (data.paused) {
        indicator.className = 'status-dot paused';
        statusText.textContent = '已暂停';
        document.getElementById('btn-pause').style.display = 'none';
        document.getElementById('btn-resume').style.display = 'inline-block';
        document.getElementById('control-auto-reply').textContent = '已暂停';
    } else {
        indicator.className = data.window_online ? 'status-dot running' : 'status-dot offline';
        statusText.textContent = data.window_online ? '运行中' : 'QQ窗口离线';
        document.getElementById('btn-pause').style.display = 'inline-block';
        document.getElementById('btn-resume').style.display = 'none';
        document.getElementById('control-auto-reply').textContent = data.window_online ? '运行中' : '离线';
    }

    windowStatus.textContent = `QQ窗口: ${data.window_title || '未检测'} ${data.window_online ? '在线' : '离线'}`;
    document.getElementById('control-qq-window').textContent = data.window_title || '未检测';

    if (data.last_reply) {
        document.getElementById('control-last-reply').textContent = data.last_reply.slice(0, 30);
    }

    const modeMap = {
        'region': '屏幕区域',
        'manual': '手动截图',
        'auto': '自动窗口'
    };
    document.getElementById('control-mode').textContent = modeMap[data.mode] || (data.mode || '自动窗口');
}

// ========== 控制按钮 ==========
async function pauseBot() {
    await fetch(`${API_BASE}/api/control/pause`, {method: 'POST'});
    fetchStatus();
}

async function resumeBot() {
    await fetch(`${API_BASE}/api/control/resume`, {method: 'POST'});
    fetchStatus();
}

async function testAPIConnection() {
    const resultDiv = document.getElementById('test-api-result');
    resultDiv.style.display = 'block';
    resultDiv.className = 'api-test-result';
    resultDiv.textContent = '正在测试连接...';

    try {
        const res = await fetch(`${API_BASE}/api/control/test-api`, {method: 'POST'});
        const data = await res.json();
        if (data.status === 'success') {
            resultDiv.className = 'api-test-result success';
            resultDiv.textContent = `连接成功！模型: ${data.model || '未知'}`;
        } else {
            resultDiv.className = 'api-test-result error';
            resultDiv.textContent = `连接失败: ${data.message}`;
        }
    } catch (e) {
        resultDiv.className = 'api-test-result error';
        resultDiv.textContent = `请求失败: ${e.message}`;
    }
}

async function switchToQQDesktop() {
    try {
        await fetch(`${API_BASE}/api/control/switch-desktop`, {method: 'POST'});
        alert('已发送切换请求（如虚拟桌面可用）');
    } catch (e) {
        alert('切换失败');
    }
}

async function clearHistory() {
    if (!confirm('确定要清空所有历史记录吗？此操作不可恢复。')) return;
    try {
        const res = await fetch(`${API_BASE}/api/control/clear-history`, {method: 'POST'});
        const data = await res.json();
        alert(data.status === 'success' ? '已清空' : '清空失败');
        loadMessages();
        loadMemory();
    } catch (e) {
        alert('清空失败');
    }
}

// ========== 手动发送 ==========
async function sendManualMessage() {
    const input = document.getElementById('manual-input');
    const message = input.value.trim();
    if (!message) return;

    try {
        const res = await fetch(`${API_BASE}/api/control/send`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message})
        });
        const data = await res.json();
        if (data.status === 'success') {
            input.value = '';
        } else {
            alert('发送失败: ' + data.message);
        }
    } catch (e) {
        alert('发送失败');
    }
}

// ========== 配置管理 ==========
let _fullConfig = {};

async function loadConfig() {
    try {
        const res = await fetch(`${API_BASE}/api/config`);
        _fullConfig = await res.json();

        // 大模型
        document.getElementById('config-base-url').value = _fullConfig.llm?.base_url || '';
        document.getElementById('config-api-key').value = _fullConfig.llm?.api_key || '';
        document.getElementById('config-model').value = _fullConfig.llm?.model || '';
        document.getElementById('config-temperature').value = _fullConfig.llm?.temperature ?? 0.7;
        document.getElementById('config-max-tokens').value = _fullConfig.llm?.max_tokens ?? 500;

        // 机器人
        document.getElementById('config-bot-name').value = _fullConfig.bot?.name || '';
        document.getElementById('config-system-prompt').value = _fullConfig.bot?.system_prompt || '';

        // 截图
        document.getElementById('config-interval').value = _fullConfig.capture?.interval ?? 10;
        document.getElementById('config-area-ratio').value = _fullConfig.capture?.message_area_ratio ?? 0.7;
        document.getElementById('config-debug-screenshots').checked = _fullConfig.capture?.debug_screenshots ?? false;

        // 过滤与记忆
        document.getElementById('config-ignore-my-msg').checked = _fullConfig.filter?.ignore_my_messages ?? true;
        document.getElementById('config-memory-enabled').checked = _fullConfig.memory?.enabled ?? true;
        document.getElementById('config-max-history').value = _fullConfig.filter?.max_history_messages ?? 10;
        document.getElementById('config-load-recent').value = _fullConfig.memory?.load_recent ?? 20;
    } catch (e) {
        console.error('加载配置失败:', e);
    }
}

async function saveConfig() {
    const update = {
        llm: {
            base_url: document.getElementById('config-base-url').value,
            api_key: document.getElementById('config-api-key').value,
            model: document.getElementById('config-model').value,
            temperature: parseFloat(document.getElementById('config-temperature').value),
            max_tokens: parseInt(document.getElementById('config-max-tokens').value)
        },
        bot: {
            name: document.getElementById('config-bot-name').value,
            system_prompt: document.getElementById('config-system-prompt').value
        },
        capture: {
            interval: parseInt(document.getElementById('config-interval').value),
            message_area_ratio: parseFloat(document.getElementById('config-area-ratio').value),
            debug_screenshots: document.getElementById('config-debug-screenshots').checked,
            window_title_keywords: ["QQ"],
            debug_dir: "debug_screenshots"
        },
        filter: {
            ignore_my_messages: document.getElementById('config-ignore-my-msg').checked,
            max_history_messages: parseInt(document.getElementById('config-max-history').value)
        },
        memory: {
            enabled: document.getElementById('config-memory-enabled').checked,
            load_recent: parseInt(document.getElementById('config-load-recent').value),
            data_dir: "data",
            split_by_date: true
        }
    };

    try {
        const res = await fetch(`${API_BASE}/api/config`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(update)
        });
        const data = await res.json();
        alert(data.status === 'success' ? data.message : '保存失败');
    } catch (e) {
        alert('保存失败');
    }
}

// ========== 聊天记录 ==========
async function loadMessages(page = 1, search = '', date = '') {
    currentPage = page;
    const pageSize = 50;

    let url = `${API_BASE}/api/messages?page=${page}&page_size=${pageSize}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    if (date) url += `&date=${date}`;

    try {
        const res = await fetch(url);
        const data = await res.json();
        renderMessages(data.items || []);
        document.getElementById('page-info').textContent =
            `第 ${page} 页 / 共 ${data.total_pages || 1} 页`;
    } catch (e) {
        console.error('加载记录失败:', e);
    }
}

function renderMessages(items) {
    const list = document.getElementById('history-list');
    if (items.length === 0) {
        list.innerHTML = '<div class="empty-tip">暂无记录</div>';
        return;
    }

    list.innerHTML = items.map(item => `
        <div class="history-item ${item.is_bot ? 'bot-item' : ''}">
            <div class="history-header">
                <span>${escapeHtml(item.sender)}</span>
                <span>${item.timestamp}</span>
            </div>
            <div>${escapeHtml(item.content)}</div>
        </div>
    `).join('');
}

async function loadDates() {
    try {
        const res = await fetch(`${API_BASE}/api/messages/dates`);
        const dates = await res.json();
        const select = document.getElementById('date-select');
        select.innerHTML = '<option value="">今天</option>' +
            dates.map(d => `<option value="${d}">${d}</option>`).join('');
    } catch (e) {
        console.error('加载日期失败:', e);
    }
}

function exportMessages() {
    const date = document.getElementById('date-select').value;
    let url = `${API_BASE}/api/messages?page=1&page_size=9999`;
    if (date) url += `&date=${date}`;

    fetch(url)
        .then(r => r.json())
        .then(data => {
            const blob = new Blob([JSON.stringify(data.items, null, 2)], {type: 'application/json'});
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = `chat_history_${date || 'today'}.json`;
            a.click();
        });
}

// ========== 记忆管理 ==========
async function loadMemory() {
    try {
        const res = await fetch(`${API_BASE}/api/messages/memory?count=50`);
        const records = await res.json();
        const list = document.getElementById('memory-list');

        if (records.length === 0) {
            list.innerHTML = '<div class="empty-tip">暂无记忆记录</div>';
            return;
        }

        list.innerHTML = records.map((item, idx) => `
            <div class="history-item ${item.is_bot ? 'bot-item' : ''}">
                <div class="history-header">
                    <span>${escapeHtml(item.sender)}</span>
                    <span>${item.timestamp}</span>
                </div>
                <div>${escapeHtml(item.content)}</div>
            </div>
        `).join('');
    } catch (e) {
        console.error('加载记忆失败:', e);
    }
}

async function clearAllMemory() {
    if (!confirm('确定要清空所有记忆吗？此操作不可恢复。')) return;
    try {
        const res = await fetch(`${API_BASE}/api/control/clear-history`, {method: 'POST'});
        const data = await res.json();
        alert(data.status === 'success' ? '已清空' : '清空失败');
        loadMemory();
    } catch (e) {
        alert('清空失败');
    }
}

// ========== 日志 ==========
async function loadLogs() {
    try {
        const res = await fetch(`${API_BASE}/api/logs`);
        const data = await res.json();
        const container = document.getElementById('log-container');

        if (!data.logs || data.logs.length === 0) {
            container.innerHTML = '<div class="empty-tip">暂无日志</div>';
            return;
        }

        container.innerHTML = data.logs.map(line => {
            let cls = 'log-line';
            if (line.includes('ERROR')) cls += ' error';
            else if (line.includes('WARNING')) cls += ' warning';
            else if (line.includes('INFO')) cls += ' info';
            return `<div class="${cls}">${escapeHtml(line)}</div>`;
        }).join('');

        container.scrollTop = container.scrollHeight;
    } catch (e) {
        document.getElementById('log-container').innerHTML =
            '<div class="empty-tip">加载日志失败</div>';
    }
}

function clearLogDisplay() {
    document.getElementById('log-container').innerHTML = '';
}

function downloadLogFile() {
    window.open(`${API_BASE}/api/logs/download`, '_blank');
}

// ========== 工具 ==========
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ========== 区域设置（启动独立浮动窗口） ==========
async function startRegionPicker() {
    try {
        const res = await fetch(`${API_BASE}/api/control/start-region-picker`, {method: 'POST'});
        const data = await res.json();
        if (data.status === 'success') {
            alert('区域选取工具已启动！\n请在屏幕右下角查看浮动窗口。\n\n操作步骤：\n1. 确保QQ窗口可见\n2. 点击 [截取屏幕]\n3. 框选消息区域，点击输入框位置\n4. 点击 [保存配置]');
        } else {
            alert('启动失败: ' + (data.message || '未知错误'));
        }
    } catch (e) {
        alert('启动区域选取工具失败');
    }
}

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', () => {
    connectWebSocket();
    fetchStatus();
    loadConfig();
    loadMessages();
    loadDates();

    // 定时刷新状态
    setInterval(fetchStatus, 3000);

    // 运行控制
    document.getElementById('btn-pause').addEventListener('click', pauseBot);
    document.getElementById('btn-resume').addEventListener('click', resumeBot);
    document.getElementById('btn-test-api').addEventListener('click', testAPIConnection);
    document.getElementById('btn-switch-desktop').addEventListener('click', switchToQQDesktop);
    document.getElementById('btn-clear-history').addEventListener('click', clearHistory);
    document.getElementById('btn-send').addEventListener('click', sendManualMessage);

    // 区域设置
    document.getElementById('btn-set-region').addEventListener('click', startRegionPicker);
    document.getElementById('manual-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendManualMessage();
    });

    // 配置
    document.getElementById('btn-save-config').addEventListener('click', saveConfig);

    // 聊天记录
    document.getElementById('btn-search').addEventListener('click', () => {
        const search = document.getElementById('search-input').value;
        const date = document.getElementById('date-select').value;
        loadMessages(1, search, date);
    });
    document.getElementById('date-select').addEventListener('change', (e) => {
        loadMessages(1, document.getElementById('search-input').value, e.target.value);
    });
    document.getElementById('btn-prev').addEventListener('click', () => {
        if (currentPage > 1) loadMessages(currentPage - 1);
    });
    document.getElementById('btn-next').addEventListener('click', () => {
        loadMessages(currentPage + 1);
    });
    document.getElementById('btn-export').addEventListener('click', exportMessages);
    document.getElementById('btn-refresh-messages').addEventListener('click', () => {
        loadMessages(currentPage);
        loadDates();
    });

    // 记忆
    document.getElementById('btn-load-memory').addEventListener('click', loadMemory);
    document.getElementById('btn-clear-memory').addEventListener('click', clearAllMemory);

    // 日志
    document.getElementById('btn-refresh-logs').addEventListener('click', loadLogs);
    document.getElementById('btn-clear-logs').addEventListener('click', clearLogDisplay);
    document.getElementById('btn-download-log').addEventListener('click', downloadLogFile);
});
