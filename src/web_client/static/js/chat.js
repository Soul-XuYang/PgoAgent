// API 基础路径
const API_BASE = '/api/v1';

// 全局状态
let currentConversationId = null;
let conversations = [];

// DOM 元素
const conversationList = document.getElementById('conversationList');
const messagesList = document.getElementById('messagesList');
const messagesContainer = document.getElementById('messagesContainer');
const emptyState = document.getElementById('emptyState');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const newChatBtn = document.getElementById('newChatBtn');
const attachBtn = document.getElementById('attachBtn');
const userNameEl = document.getElementById('userName');
const settingsBtn = document.getElementById('settingsBtn');

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    loadUserInfo();
    loadConversations();
    setupEventListeners();
});

// 设置事件监听
function setupEventListeners() {
    sendBtn.addEventListener('click', handleSendMessage);
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    });
    
    // 自动调整输入框高度
    messageInput.addEventListener('input', () => {
        messageInput.style.height = '24px';
        messageInput.style.height = `${Math.min(messageInput.scrollHeight, 200)}px`;
    });

    newChatBtn.addEventListener('click', handleNewChat);
    attachBtn.addEventListener('click', handleAttach);
    settingsBtn.addEventListener('click', handleSettings);
}

// 加载用户信息
async function loadUserInfo() {
    try {
        // TODO: 从 JWT token 中解析用户名，或调用 API
        // 临时使用 localStorage 或从后端获取
        const token = getCookie('Authorization');
        if (token) {
            // 可以从 token 中解析，这里先使用默认值
            userNameEl.textContent = '用户';
        }
    } catch (error) {
        console.error('Failed to load user info:', error);
    }
}

// 加载对话列表
async function loadConversations() {
    try {
        conversationList.innerHTML = '<div class="list-loading">加载中...</div>';
        
        const response = await fetch(`${API_BASE}/conversations`, {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        if (response.ok) {
            const data = await response.json();
            conversations = data.conversations || [];
            renderConversations(conversations);
        } else {
            conversationList.innerHTML = '<div class="list-loading">暂无对话</div>';
        }
    } catch (error) {
        console.error('Failed to load conversations:', error);
        conversationList.innerHTML = '<div class="list-loading">加载失败</div>';
    }
}

// 渲染对话列表
function renderConversations(convs) {
    if (!convs || convs.length === 0) {
        conversationList.innerHTML = '<div class="list-loading">暂无对话</div>';
        return;
    }

    // 按日期分组
    const grouped = groupConversationsByDate(convs);
    let html = '';

    for (const [dateLabel, items] of Object.entries(grouped)) {
        html += `<div class="conversation-date-group">${dateLabel}</div>`;
        items.forEach(conv => {
            html += `
                <div class="conversation-item ${conv.id === currentConversationId ? 'active' : ''}" 
                     data-conversation-id="${conv.id}">
                    ${escapeHtml(conv.conversation_name || '未命名对话')}
                </div>
            `;
        });
    }

    conversationList.innerHTML = html;

    // 添加点击事件
    conversationList.querySelectorAll('.conversation-item').forEach(item => {
        item.addEventListener('click', () => {
            const id = item.dataset.conversationId;
            loadConversation(id);
        });
    });
}

// 按日期分组对话
function groupConversationsByDate(convs) {
    const groups = {
        '今天': [],
        '昨天': [],
        '7天内': [],
        '更早': []
    };

    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const weekAgo = new Date(today);
    weekAgo.setDate(weekAgo.getDate() - 7);

    convs.forEach(conv => {
        const date = new Date(conv.last_msg_time || conv.created_at);
        
        if (date >= today) {
            groups['今天'].push(conv);
        } else if (date >= yesterday) {
            groups['昨天'].push(conv);
        } else if (date >= weekAgo) {
            groups['7天内'].push(conv);
        } else {
            groups['更早'].push(conv);
        }
    });

    // 移除空组
    Object.keys(groups).forEach(key => {
        if (groups[key].length === 0) {
            delete groups[key];
        }
    });

    return groups;
}

// 加载对话消息
async function loadConversation(conversationId) {
    try {
        currentConversationId = conversationId;
        
        // 更新对话列表的激活状态
        conversationList.querySelectorAll('.conversation-item').forEach(item => {
            item.classList.toggle('active', item.dataset.conversationId === conversationId);
        });

        const response = await fetch(`${API_BASE}/conversations/${conversationId}/messages`, {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        if (response.ok) {
            const data = await response.json();
            const messages = data.messages || [];
            renderMessages(messages);
            emptyState.style.display = 'none';
            messagesList.style.display = 'block';
            scrollToBottom();
        }
    } catch (error) {
        console.error('Failed to load conversation:', error);
    }
}

// 渲染消息
function renderMessages(messages) {
    if (!messages || messages.length === 0) {
        messagesList.innerHTML = '';
        return;
    }

    let html = '';
    messages.forEach(msg => {
        const isUser = msg.role === 'user';
        const time = formatTime(msg.created_at);
        
        html += `
            <div class="message ${isUser ? 'message-user' : ''}">
                <div class="message-avatar">
                    ${isUser 
                        ? '<svg viewBox="0 0 24 24" fill="none"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="7" r="4" stroke="currentColor" stroke-width="2"/></svg>'
                        : '<svg viewBox="0 0 24 24" fill="none"><path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
                    }
                </div>
                <div class="message-content">
                    <div class="message-text">${escapeHtml(msg.content)}</div>
                    <div class="message-time">${time}</div>
                </div>
            </div>
        `;
    });

    messagesList.innerHTML = html;
}

// 发送消息
async function handleSendMessage() {
    const content = messageInput.value.trim();
    if (!content) return;

    // 获取对话模式
    const chatMode = document.querySelector('input[name="chatMode"]:checked').value;

    // 清空输入框
    messageInput.value = '';
    messageInput.style.height = '24px';

    // 如果没有当前对话，创建新对话（首次发送消息时）
    if (!currentConversationId) {
        try {
            const response = await fetch(`${API_BASE}/conversations`, {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    conversation_id: '', // 首次创建时为空，后端自动生成
                    user_query: content // 用户的首条消息
                }),
            });

            if (response.ok) {
                const data = await response.json();
                currentConversationId = data.conversation_id;
                
                // 重新加载对话列表（包含新创建的对话）
                loadConversations();
                
                // 重新加载该对话的消息（因为后端已经写入了首条 user 和 assistant 消息）
                await loadConversation(currentConversationId);
            } else {
                const error = await response.json();
                alert(error.error || '创建对话失败，请稍后重试');
                return;
            }
        } catch (error) {
            console.error('Failed to create conversation:', error);
            alert('创建对话失败，请稍后重试');
            return;
        }
    } else {
        // 已有对话，继续发送消息
        // 显示用户消息
        appendMessage('user', content);

        try {
            const response = await fetch(`${API_BASE}/conversations/${currentConversationId}/messages`, {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    content: content,
                    chat_mode: chatMode
                }),
            });

            if (response.ok) {
                if (chatMode === 'stream') {
                    // 流式响应处理
                    await handleStreamResponse(response);
                } else {
                    // 非流式响应处理
                    const data = await response.json();
                    if (data.response) {
                        appendMessage('assistant', data.response, data.created_at, data.token_usage);
                    }
                }
                // 重新加载对话列表以更新最后消息时间
                loadConversations();
            } else {
                const error = await response.json();
                alert(error.error || '发送失败');
            }
        } catch (error) {
            console.error('Failed to send message:', error);
            alert('发送失败，请稍后重试');
        }
    }
}

// 处理流式响应
async function handleStreamResponse(response) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let aiMessageElement = null;
    let fullContent = '';
    let finalTime = null;
    let finalTokenUsage = null;

    // 创建AI消息占位符
    const time = formatTime(new Date().toISOString());
    const messageHtml = `
        <div class="message">
            <div class="message-avatar">
                <svg viewBox="0 0 24 24" fill="none"><path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </div>
            <div class="message-content">
                <div class="message-text" id="streamingMessage"></div>
                <div class="message-time">${time}</div>
            </div>
        </div>
    `;
    messagesList.insertAdjacentHTML('beforeend', messageHtml);
    aiMessageElement = document.getElementById('streamingMessage');
    scrollToBottom();

    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        if (data.content) {
                            fullContent += data.content;
                            if (aiMessageElement) {
                                aiMessageElement.textContent = fullContent;
                                scrollToBottom();
                            }
                        }
                        if (data.final) {
                            // 流式结束，更新时间和token usage
                            finalTime = data.created_at;
                            finalTokenUsage = data.token_usage;
                            const timeEl = aiMessageElement.parentElement.querySelector('.message-time');
                            if (timeEl && finalTime) {
                                timeEl.textContent = formatDate(finalTime) + (finalTokenUsage ? ` · Token: ${finalTokenUsage}` : '');
                            }
                        }
                    } catch (e) {
                        console.error('Failed to parse stream data:', e);
                    }
                }
            }
        }
    } finally {
        reader.releaseLock();
        // 移除临时ID
        if (aiMessageElement) {
            aiMessageElement.removeAttribute('id');
        }
    }
}

// 注意：createNewConversation 函数已移除
// 现在创建对话的逻辑已整合到 handleSendMessage 中
// 当用户首次发送消息时，会自动创建对话并写入首条消息

// 添加消息到界面
function appendMessage(role, content, createdAt, tokenUsage) {
    emptyState.style.display = 'none';
    messagesList.style.display = 'block';

    const isUser = role === 'user';
    const time = createdAt ? formatDate(createdAt) : formatTime(new Date().toISOString());

    const messageHtml = `
        <div class="message ${isUser ? 'message-user' : ''}">
            <div class="message-avatar">
                ${isUser 
                    ? '<svg viewBox="0 0 24 24" fill="none"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="7" r="4" stroke="currentColor" stroke-width="2"/></svg>'
                    : '<svg viewBox="0 0 24 24" fill="none"><path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
                }
            </div>
            <div class="message-content">
                <div class="message-text">${escapeHtml(content)}</div>
                <div class="message-time">${time}${tokenUsage ? ` · Token: ${tokenUsage}` : ''}</div>
            </div>
        </div>
    `;

    messagesList.insertAdjacentHTML('beforeend', messageHtml);
    scrollToBottom();
}

// 格式化日期为 2026-1-11 格式
function formatDate(dateString) {
    const date = new Date(dateString);
    const year = date.getFullYear();
    const month = date.getMonth() + 1;
    const day = date.getDate();
    return `${year}-${month}-${day}`;
}

// 滚动到底部
function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// 新建对话
function handleNewChat() {
    currentConversationId = null;
    messagesList.innerHTML = '';
    messagesList.style.display = 'none';
    emptyState.style.display = 'block';
    messageInput.focus();
}

// 附件
function handleAttach() {
    alert('附件功能待实现');
}

// 设置
function handleSettings() {
    alert('设置功能待实现');
}

// 工具函数
function formatTime(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const diff = now - date;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return '刚刚';
    if (minutes < 60) return `${minutes}分钟前`;
    if (hours < 24) return `${hours}小时前`;
    if (days < 7) return `${days}天前`;
    
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}
