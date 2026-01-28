// API 基础路径
const API_BASE = '/api/v1';

// 全局状态
let currentConversationId = null;
let conversations = [];

// 消息分页相关常量 & 状态（上滑加载更多）
const MESSAGES_PAGE_SIZE = 20; // 和后端 PAGE_SIZE 保持一致
// 每个会话的分页状态：{ hasMore, isLoading, oldestMessage }
const messagesPagination = {};

// DOM 元素（延迟获取，确保DOM已加载）
let conversationList, messagesList, messagesContainer, emptyState;
let messageInput, sendBtn, newChatBtn, attachBtn, userNameEl;
let settingsBtn, settingsMenu, memorySettingsBtn, logoutMenuBtn;
let memoryModal, memoryOverlay, memoryClose;
let loadMemoryBtn, saveMemoryBtn, deleteMemoryBtn;
let memoryTextarea, memoryEditor, memoryMeta;
// 流式对话状态 & 发送按钮图标
let isStreaming = false;
let currentStreamAbortController = null;
let sendBtnDefaultIconHTML = '';

// 获取DOM元素的函数
function getDOMElements() {
    conversationList = document.getElementById('conversationList');
    messagesList = document.getElementById('messagesList');
    messagesContainer = document.getElementById('messagesContainer');
    emptyState = document.getElementById('emptyState');
    messageInput = document.getElementById('messageInput');
    sendBtn = document.getElementById('sendBtn');
    newChatBtn = document.getElementById('newChatBtn');
    attachBtn = document.getElementById('attachBtn');
    userNameEl = document.getElementById('userName');
    settingsBtn = document.getElementById('settingsBtn');
    settingsMenu = document.getElementById('settingsMenu');
    memorySettingsBtn = document.getElementById('memorySettingsBtn');
    logoutMenuBtn = document.getElementById('logoutMenuBtn');
    memoryModal = document.getElementById('memoryModal');
    memoryOverlay = document.getElementById('memoryOverlay');
    memoryClose = document.getElementById('memoryClose');
    loadMemoryBtn = document.getElementById('loadMemoryBtn');
    saveMemoryBtn = document.getElementById('saveMemoryBtn');
    deleteMemoryBtn = document.getElementById('deleteMemoryBtn');
    memoryTextarea = document.getElementById('memoryTextarea');
    memoryEditor = document.getElementById('memoryEditor');
    memoryMeta = document.getElementById('memoryMeta');

    // 记录发送按钮的默认图标 HTML，后续切换为“停止”图标时可还原
    if (sendBtn) {
        sendBtnDefaultIconHTML = sendBtn.innerHTML;
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    // 首先获取所有DOM元素
    getDOMElements();
    // 然后加载数据和设置事件监听
    loadUserInfo();
    loadConversations();
    setupEventListeners();
});

// 设置事件监听
function setupEventListeners() {
    // 发送按钮：空闲时发送消息，流式生成时为“停止”按钮
    sendBtn.addEventListener('click', handleSendOrCancel);
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendOrCancel();
        }
    });
    
    // 自动调整输入框高度
    messageInput.addEventListener('input', () => {
        messageInput.style.height = '24px';
        messageInput.style.height = `${Math.min(messageInput.scrollHeight, 200)}px`;
    });

    newChatBtn.addEventListener('click', handleNewChat);
    attachBtn.addEventListener('click', handleAttach);
    
    // 设置按钮事件监听
    if (settingsBtn) {
        settingsBtn.addEventListener('click', handleSettings);
    } else {
        console.error('Settings button not found');
    }
    
    // 设置菜单相关事件
    if (memorySettingsBtn) {
        memorySettingsBtn.addEventListener('click', openMemoryModal);
    }
    if (logoutMenuBtn) {
        logoutMenuBtn.addEventListener('click', handleLogout);
    }
    
    // 记忆体设置大窗相关事件
    if (memoryOverlay) {
        memoryOverlay.addEventListener('click', closeMemoryModal);
    }
    if (memoryClose) {
        memoryClose.addEventListener('click', closeMemoryModal);
    }
    
    // ESC键关闭记忆体设置大窗
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && memoryModal && memoryModal.classList.contains('show')) {
            closeMemoryModal();
        }
    });
    
    // 聊天消息区域滚动加载（上滑加载更多消息）
    if (messagesContainer) {
        messagesContainer.addEventListener('scroll', handleMessagesScroll);
    }

    // 长期记忆相关事件
    if (loadMemoryBtn) {
        loadMemoryBtn.addEventListener('click', loadUserMemory);
    }
    if (saveMemoryBtn) {
        saveMemoryBtn.addEventListener('click', saveUserMemory);
    }
    if (deleteMemoryBtn) {
        deleteMemoryBtn.addEventListener('click', deleteUserMemory);
    }
    
    // 点击外部关闭设置菜单
    document.addEventListener('click', (e) => {
        if (settingsMenu && settingsBtn && 
            !settingsMenu.contains(e.target) && 
            !settingsBtn.contains(e.target) &&
            settingsMenu.style.display !== 'none') {
            settingsMenu.style.display = 'none';
        }
    });
}

// 加载用户信息
async function loadUserInfo() {
    try {
        const response = await fetch(`${API_BASE}/profile`, {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        if (response.ok) {
            const data = await response.json();
            if (data.user_name) {
                userNameEl.textContent = data.user_name;
            }

            // 根据返回的星期几，更新欢迎文案
            const welcomeTitle = document.getElementById('welcomeTitle');
            if (welcomeTitle && data.weekday) {
                welcomeTitle.textContent = `今天是${data.weekday}，PgoAgent 有什么可以帮助你的？`;
            }
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
            // 后端返回的是 { "conversations": [...] }，确保正确解析
            conversations = (data.conversations || data.Conversations || []);
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
    // 过滤掉没有有效 ID 的脏数据，避免出现 undefined 的会话项
    const validConvs = (convs || []).filter(conv => conv && conv.id && conv.id !== 'undefined');

    if (!validConvs || validConvs.length === 0) {
        conversationList.innerHTML = '<div class="list-loading">暂无对话</div>';
        return;
    }

    // 按日期分组
    const grouped = groupConversationsByDate(validConvs);
    let html = '';

    for (const [dateLabel, items] of Object.entries(grouped)) {
        html += `<div class="conversation-date-group">${dateLabel}</div>`;
        items.forEach(conv => {
            const title = escapeHtml(conv.conversation_name || '未命名对话');
            html += `
                <div class="conversation-item ${conv.id === currentConversationId ? 'active' : ''}" 
                     data-conversation-id="${conv.id}">
                    <div class="conversation-title">${title}</div>
                    <div class="conversation-actions">
                        <button class="conversation-menu-btn" data-menu-button data-conversation-id="${conv.id}" title="更多操作">
                            <svg viewBox="0 0 24 24" fill="none">
                                <circle cx="5" cy="12" r="1.5" fill="currentColor"></circle>
                                <circle cx="12" cy="12" r="1.5" fill="currentColor"></circle>
                                <circle cx="19" cy="12" r="1.5" fill="currentColor"></circle>
                            </svg>
                        </button>
                    </div>
                </div>
            `;
        });
    }

    conversationList.innerHTML = html;

    // 添加点击事件：点击标题区域切换会话
    conversationList.querySelectorAll('.conversation-item').forEach(item => {
        const id = item.dataset.conversationId;
        const titleEl = item.querySelector('.conversation-title');
        if (titleEl) {
            titleEl.addEventListener('click', () => {
                loadConversation(id);
            });
        } else {
            // 兼容性兜底
            item.addEventListener('click', () => {
                loadConversation(id);
            });
        }
    });

    // 为每个“更多”按钮绑定删除菜单
    setupConversationMenus();
}

// 为会话项绑定更多操作菜单（只实现删除）
function setupConversationMenus() {
    // 先移除页面上已有的菜单
    document.querySelectorAll('.conversation-menu').forEach(menu => menu.remove());

    const buttons = conversationList.querySelectorAll('[data-menu-button]');
    buttons.forEach(btn => {
        btn.addEventListener('click', (event) => {
            event.stopPropagation();

            // 删除其他已打开的菜单
            document.querySelectorAll('.conversation-menu').forEach(menu => menu.remove());

            const convId = btn.dataset.conversationId;
            const rect = btn.getBoundingClientRect();

            const menu = document.createElement('div');
            menu.className = 'conversation-menu';
            menu.innerHTML = `
                <div class="conversation-menu-item danger" data-action="delete" data-conversation-id="${convId}">
                    删除
                </div>
            `;

            document.body.appendChild(menu);
            const top = rect.bottom + window.scrollY;
            const left = rect.right + window.scrollX - menu.offsetWidth;
            menu.style.top = `${top}px`;
            menu.style.left = `${left}px`;

            // 点击菜单项：删除会话
            menu.querySelector('[data-action="delete"]').addEventListener('click', async (e) => {
                e.stopPropagation();
                menu.remove();
                await handleDeleteConversation(convId);
            });
        });
    });

    // 全局点击关闭菜单
    document.addEventListener('click', () => {
        document.querySelectorAll('.conversation-menu').forEach(menu => menu.remove());
    }, { once: true });
}

// 删除会话（调用后端 DELETE /api/v1/conversations/:id）
async function handleDeleteConversation(conversationId) {
    if (!conversationId) return;

    const confirmDelete = window.confirm('确定要删除该对话吗？此操作不可恢复。');
    if (!confirmDelete) return;

    try {
        const response = await fetch(`${API_BASE}/conversations/${conversationId}`, {
            method: 'DELETE',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            alert(error.error || '删除对话失败，请稍后重试');
            return;
        }

        // 如果删除的是当前会话，清空右侧消息并恢复空状态
        if (currentConversationId === conversationId) {
            currentConversationId = null;
            messagesList.innerHTML = '';
            messagesList.style.display = 'none';
            emptyState.style.display = 'block';
        }

        // 重新加载对话列表
        await loadConversations();
    } catch (error) {
        console.error('Failed to delete conversation:', error);
        alert('删除对话失败，请稍后重试');
    }
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
        // 优先使用 last_msg_time（最后消息时间），如果没有则使用 created_at
        const dateStr = conv.last_msg_time || conv.lastMsgTime || conv.CreatedAt;
        const date = new Date(dateStr);
        
        // 检查日期是否有效
        if (isNaN(date.getTime())) {
            groups['更早'].push(conv);
            return;
        }
        
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

// 加载对话消息（支持分页，首次加载最新一页）
async function loadConversation(conversationId) {
    try {
        currentConversationId = conversationId;

        // 初始化当前会话的分页状态
        messagesPagination[currentConversationId] = {
            hasMore: true,
            isLoading: false,
            oldestMessage: null,
        };

        // 更新对话列表的激活状态
        conversationList.querySelectorAll('.conversation-item').forEach(item => {
            item.classList.toggle('active', item.dataset.conversationId === conversationId);
        });

        const response = await fetch(`${API_BASE}/conversations/${conversationId}/messages?limit=${MESSAGES_PAGE_SIZE}`, {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        if (response.ok) {
            const data = await response.json();
            // 适配新的消息格式：支持 messages 和 Messages 字段
            const messages = data.messages || data.Messages || [];

            // 记录当前会话最早一条消息，用于后续 before_* 查询
            if (messages.length > 0) {
                const oldest = messages[0];
                messagesPagination[currentConversationId].oldestMessage = oldest;
                messagesPagination[currentConversationId].hasMore = messages.length === MESSAGES_PAGE_SIZE;
            } else {
                messagesPagination[currentConversationId].hasMore = false;
            }

            // 首次加载渲染整页
            renderInitialMessages(messages);
            emptyState.style.display = 'none';
            messagesList.style.display = 'block';
            scrollToBottom();
        }
    } catch (error) {
        console.error('Failed to load conversation:', error);
    }
}

// 处理消息列表滚动（上滑加载更多历史记录）
function handleMessagesScroll() {
    if (!messagesContainer || !currentConversationId) return;

    const pagination = messagesPagination[currentConversationId];
    if (!pagination || pagination.isLoading || !pagination.hasMore) return;

    // 当滚动接近顶部时加载更多历史消息
    const threshold = 40; // 距顶部 40px 内触发
    if (messagesContainer.scrollTop <= threshold) {
        loadMoreMessages(currentConversationId);
    }
}

// 加载更多历史消息（基于 before_created_at + before_id 分页）
async function loadMoreMessages(conversationId) {
    const pagination = messagesPagination[conversationId];
    if (!pagination || pagination.isLoading || !pagination.hasMore || !pagination.oldestMessage) return;

    const oldest = pagination.oldestMessage;
    const oldestCreatedAt = getMessageCreatedAt(oldest);
    const oldestId = oldest.id;

    if (!oldestCreatedAt || !oldestId) {
        pagination.hasMore = false;
        return;
    }

    pagination.isLoading = true;

    try {
        const params = new URLSearchParams({
            limit: String(MESSAGES_PAGE_SIZE),
            before_created_at: oldestCreatedAt,
            before_id: oldestId,
        });

        const response = await fetch(
            `${API_BASE}/conversations/${conversationId}/messages?${params.toString()}`,
            {
                method: 'GET',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                },
            }
        );

        if (!response.ok) {
            pagination.isLoading = false;
            return;
        }

        const data = await response.json();
        const messages = data.messages || data.Messages || [];

        if (messages.length === 0) {
            pagination.hasMore = false;
            pagination.isLoading = false;
            return;
        }

        // 更新最早一条消息 & 是否还有更多
        pagination.oldestMessage = messages[0];
        pagination.hasMore = messages.length === MESSAGES_PAGE_SIZE;

        // 向顶部插入更早消息，保持当前视口位置
        prependMessages(messages);
    } catch (error) {
        console.error('Failed to load more messages:', error);
    } finally {
        pagination.isLoading = false;
    }
}

// 渲染消息（首次加载一页，适配新的 Message 格式：role, content, created_at）
function renderInitialMessages(messages) {
    if (!messages || messages.length === 0) {
        messagesList.innerHTML = '';
        return;
    }

    let html = '';
    messages.forEach(msg => {
        html += buildMessageHtml(msg);
    });

    messagesList.innerHTML = html;
}

// 兼容旧代码中的 renderMessages 调用，内部复用 renderInitialMessages
// TODO: 如后续有更复杂的渲染需求，可在此扩展
function renderMessages(messages) {
    renderInitialMessages(messages);
}

// 向顶部追加更早的消息（用于上滑加载历史）
function prependMessages(messages) {
    if (!messages || messages.length === 0) return;

    let html = '';
    messages.forEach(msg => {
        html += buildMessageHtml(msg);
    });

    // 记录加载前的滚动高度，加载后保持视口位置不跳动
    const previousScrollHeight = messagesContainer.scrollHeight;
    messagesList.insertAdjacentHTML('afterbegin', html);
    const newScrollHeight = messagesContainer.scrollHeight;
    messagesContainer.scrollTop = newScrollHeight - previousScrollHeight + messagesContainer.scrollTop;
}

// 构造单条消息的 HTML，适配新的消息结构
function buildMessageHtml(msg) {
    // 适配新的消息格式：role, content, created_at
    const role = msg.role || '';
    const content = msg.content || '';
    const createdAt = getMessageCreatedAt(msg);

    const isUser = role === 'user';
    const time = createdAt ? formatTime(createdAt) : '刚刚';

    return `
        <div class="message ${isUser ? 'message-user' : ''}">
            <div class="message-avatar">
                ${isUser 
                    ? '<svg viewBox="0 0 24 24" fill="none"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="7" r="4" stroke="currentColor" stroke-width="2"/></svg>'
                    : '<svg viewBox="0 0 24 24" fill="none"><path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
                }
            </div>
            <div class="message-content">
                <div class="message-text">${formatMessageContent(content)}</div>
                <div class="message-time">${time}</div>
            </div>
        </div>
    `;
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
        // 立即跳转到对话界面并显示加载动画
        emptyState.style.display = 'none';
        messagesList.style.display = 'block';
        messagesList.innerHTML = ''; // 清空旧消息
        
        // 显示 AI 回复的加载动画
        showLoadingMessage();
        
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
                
                // 移除加载动画
                hideLoadingMessage();
                
                // 直接使用后端返回的 Messages 渲染（包含首条 user 和 assistant 消息）
                if (data.messages && Array.isArray(data.messages) && data.messages.length > 0) {
                    renderMessages(data.messages);
                    scrollToBottom();
                } else {
                    // 如果后端没有返回 messages，则重新加载（兼容性处理）
                    await loadConversation(currentConversationId);
                }
                
                // 重新加载对话列表（包含新创建的对话）
                loadConversations();
            } else {
                // 移除加载动画
                hideLoadingMessage();
                const error = await response.json();
                alert(error.error || '创建对话失败，请稍后重试');
                // 恢复空状态
                messagesList.style.display = 'none';
                emptyState.style.display = 'block';
                return;
            }
        } catch (error) {
            // 移除加载动画
            hideLoadingMessage();
            console.error('Failed to create conversation:', error);
            alert('创建对话失败，请稍后重试');
            // 恢复空状态
            messagesList.style.display = 'none';
            emptyState.style.display = 'block';
            return;
        }
    } else {
        // 已有对话，继续发送消息
        // 显示用户消息
        appendMessage('user', content);
        
        // 显示 AI 回复的加载动画
        showLoadingMessage();

        try {
            // 流式模式下，使用 AbortController 以支持前端中断
            let controller = null;
            if (chatMode === 'stream') {
                controller = new AbortController();
                currentStreamAbortController = controller;
                isStreaming = true;
                updateSendButtonState();
            }

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
                signal: controller ? controller.signal : undefined,
            });

            if (response.ok) {
                // 移除加载动画
                hideLoadingMessage();
                
                if (chatMode === 'stream') {
                    // 流式响应处理
                    try {
                        await handleStreamResponse(response);
                    } finally {
                        isStreaming = false;
                        currentStreamAbortController = null;
                        updateSendButtonState();
                    }
                } else {
                    // 非流式响应处理
                    const data = await response.json();
                    // 适配后端返回格式：{ message: { role, content, created_at }, token_usage }
                    if (data.message && data.message.content) {
                        appendMessage('assistant', data.message.content, data.message.created_at, data.token_usage);
                    } else if (data.response) {
                        // 兼容旧格式
                        appendMessage('assistant', data.response, data.created_at, data.token_usage);
                    }
                }
                // 重新加载对话列表以更新最后消息时间
                loadConversations();
            } else {
                // 移除加载动画
                hideLoadingMessage();
                const error = await response.json();
                alert(error.error || '发送失败');
            }
        } catch (error) {
            // 如果是手动中断（AbortError），静默处理即可
            if (error.name === 'AbortError') {
                console.debug('Stream request aborted by user');
            } else {
                hideLoadingMessage();
                console.error('Failed to send message:', error);
                alert('发送失败，请稍后重试');
            }
        }
    }
}

// 发送按钮统一入口：未在流式中则发送，流式中则执行“停止生成”
async function handleSendOrCancel() {
    if (isStreaming) {
        await cancelCurrentStream();
    } else {
        await handleSendMessage();
    }
}

// 前端取消当前流式响应，并通知后端中断 gRPC 任务
async function cancelCurrentStream() {
    // 先本地中止 SSE 读取
    if (currentStreamAbortController) {
        currentStreamAbortController.abort();
        currentStreamAbortController = null;
    }
    isStreaming = false;
    updateSendButtonState();

    if (!currentConversationId) return;

    try {
        await fetch(`${API_BASE}/conversations/${currentConversationId}/cancel`, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
            },
        });
    } catch (error) {
        console.error('Failed to cancel conversation task:', error);
    }
}

// 处理流式响应
async function handleStreamResponse(response) {
    // 先移除加载动画（如果有）
    hideLoadingMessage();
    
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
                        
                        // 处理内容更新
                        if (data.content) {
                            // 判断是否是节点状态消息（通过 node_name 或内容特征）
                            const isStatusMessage = data.node_name && data.node_name !== '' ||
                                data.content.includes('正在思考') || data.content.includes('正在决策') || 
                                data.content.includes('正在使用工具') || data.content.includes('正在总结') ||
                                data.content.includes('正在执行') || data.content.includes('正在计划') ||
                                data.content.includes('Pgo大模型正在') || data.content.includes('Pgo正在');
                            
                            if (isStatusMessage) {
                                // 这是节点状态消息，直接替换显示（不追加到fullContent）
                                if (aiMessageElement) {
                                    aiMessageElement.textContent = data.content;
                                    scrollToBottom();
                                }
                            } else {
                                // 这是实际内容，追加显示
                                fullContent += data.content;
                                if (aiMessageElement) {
                                    aiMessageElement.textContent = fullContent;
                                    scrollToBottom();
                                }
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

// 根据当前流式状态更新发送按钮的图标与样式
function updateSendButtonState() {
    if (!sendBtn) return;
    if (isStreaming) {
        sendBtn.classList.add('is-streaming');
        sendBtn.title = '停止生成';
        // 使用一个简单的黑色方块作为“停止”图标
        sendBtn.innerHTML = '<span class="stop-icon"></span>';
    } else {
        sendBtn.classList.remove('is-streaming');
        sendBtn.title = '发送';
        if (sendBtnDefaultIconHTML) {
            sendBtn.innerHTML = sendBtnDefaultIconHTML;
        }
    }
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

// 设置 - 显示设置菜单
function handleSettings(e) {
    if (!settingsMenu || !settingsBtn) {
        console.error('Settings menu or button not found', { settingsMenu, settingsBtn });
        // 如果找不到元素，显示提示（调试用）
        if (!settingsMenu) {
            console.error('settingsMenu element not found');
        }
        if (!settingsBtn) {
            console.error('settingsBtn element not found');
        }
        return;
    }
    
    if (e) {
        e.stopPropagation();
        e.preventDefault();
    }
    
    // 先关闭其他菜单
    document.querySelectorAll('.conversation-menu').forEach(menu => menu.remove());
    
    // 切换菜单显示状态
    const isVisible = settingsMenu.style.display === 'block' || 
                     window.getComputedStyle(settingsMenu).display === 'block';
    
    if (isVisible) {
        // 如果已经显示，则关闭
        settingsMenu.style.display = 'none';
        return;
    }
    
    // 获取设置按钮位置
    const rect = settingsBtn.getBoundingClientRect();
    
    // 设置菜单样式和位置
    settingsMenu.style.position = 'fixed';
    settingsMenu.style.zIndex = '1000';
    
    // 临时显示菜单以获取宽度
    settingsMenu.style.visibility = 'hidden';
    settingsMenu.style.display = 'block';
    const menuWidth = settingsMenu.offsetWidth || 200;
    settingsMenu.style.visibility = 'visible';
    
    // 计算位置：在按钮上方显示
    const top = rect.top - settingsMenu.offsetHeight - 4;
    const left = Math.max(4, rect.right - menuWidth);
    
    settingsMenu.style.top = `${Math.max(4, top)}px`;
    settingsMenu.style.left = `${left}px`;
    settingsMenu.style.display = 'block';
}

// 打开记忆体设置大窗
function openMemoryModal() {
    if (memoryModal) {
        // 先关闭设置菜单
        if (settingsMenu) {
            settingsMenu.style.display = 'none';
        }
        // 打开记忆体设置大窗
        memoryModal.style.display = 'flex';
        // 使用requestAnimationFrame确保动画触发
        requestAnimationFrame(() => {
            memoryModal.classList.add('show');
        });
        document.body.style.overflow = 'hidden';
        // 自动加载记忆数据
        loadUserMemory();
    }
}

// 关闭记忆体设置大窗
function closeMemoryModal() {
    if (memoryModal) {
        memoryModal.classList.remove('show');
        // 延迟移除display，让动画完成
        setTimeout(() => {
            if (!memoryModal.classList.contains('show')) {
                memoryModal.style.display = 'none';
            }
        }, 300);
        document.body.style.overflow = '';
    }
}

// 退出登录
async function handleLogout() {
    const confirmLogout = window.confirm('确定要退出登录吗？');
    if (!confirmLogout) return;
    
    try {
        const response = await fetch(`${API_BASE}/auth/logout`, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
            },
        });
        
        if (response.ok) {
            // 退出成功，跳转到登录页
            window.location.href = '/';
        } else {
            const error = await response.json().catch(() => ({}));
            alert(error.error || '退出登录失败，请稍后重试');
        }
    } catch (error) {
        console.error('Failed to logout:', error);
        alert('退出登录失败，请稍后重试');
    }
}

// 加载用户长期记忆
async function loadUserMemory() {
    if (!loadMemoryBtn) return;
    
    const originalText = loadMemoryBtn.querySelector('span')?.textContent || loadMemoryBtn.textContent;
    loadMemoryBtn.disabled = true;
    if (loadMemoryBtn.querySelector('span')) {
        loadMemoryBtn.querySelector('span').textContent = '加载中...';
    } else {
        loadMemoryBtn.textContent = '加载中...';
    }
    
    try {
        const response = await fetch(`${API_BASE}/profile/store`, {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
            },
        });
        
        if (response.ok) {
            const data = await response.json();
            
            // 解析 value JSON - 支持多种字段名格式（兼容大小写）
            let memoryText = '';
            let updatedAt = '';
            
            // 尝试多种可能的字段名：value, Value
            const valueData = data.value || data.Value;
            
            if (valueData) {
                try {
                    // datatypes.JSON 可能已经是对象，也可能是字符串
                    const valueObj = typeof valueData === 'string' ? JSON.parse(valueData) : valueData;
                    memoryText = valueObj.memory || valueObj.Memory || '';
                } catch (e) {
                    console.error('Failed to parse memory value:', e);
                }
            }
            
            // 尝试多种可能的更新时间字段名
            const updateTime = data.updated_at || data.UpdatedAt || data.updatedAt;
            if (updateTime) {
                updatedAt = formatDateTime(updateTime);
            }
            
            // 显示内容
            if (memoryTextarea) {
                memoryTextarea.value = memoryText || '';
            }
            if (memoryEditor) {
                memoryEditor.style.display = 'block';
            }
            if (memoryMeta) {
                memoryMeta.innerHTML = updatedAt ? `<div class="memory-updated"><svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/><polyline points="12 6 12 12 16 14" stroke="currentColor" stroke-width="2"/></svg>最后更新：${updatedAt}</div>` : '';
            }
            
            if (loadMemoryBtn.querySelector('span')) {
                loadMemoryBtn.querySelector('span').textContent = '重新加载';
            } else {
                loadMemoryBtn.textContent = '重新加载';
            }
        } else {
            if (response.status === 404 || response.status === 500) {
                // 没有数据或查询失败
                if (memoryTextarea) {
                    memoryTextarea.value = '';
                }
                if (memoryEditor) {
                    memoryEditor.style.display = 'block';
                }
                if (memoryMeta) {
                    memoryMeta.innerHTML = '<div class="memory-empty"><svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/><line x1="12" y1="8" x2="12" y2="12" stroke="currentColor" stroke-width="2"/><line x1="12" y1="16" x2="12.01" y2="16" stroke="currentColor" stroke-width="2"/></svg>暂无长期记忆数据</div>';
                }
                if (loadMemoryBtn.querySelector('span')) {
                    loadMemoryBtn.querySelector('span').textContent = '加载记忆';
                } else {
                    loadMemoryBtn.textContent = '加载记忆';
                }
            } else {
                const error = await response.json().catch(() => ({}));
                alert(error.error || '加载长期记忆失败');
                if (loadMemoryBtn.querySelector('span')) {
                    loadMemoryBtn.querySelector('span').textContent = '加载记忆';
                } else {
                    loadMemoryBtn.textContent = '加载记忆';
                }
            }
        }
    } catch (error) {
        console.error('Failed to load user memory:', error);
        alert('加载长期记忆失败，请稍后重试');
        if (loadMemoryBtn.querySelector('span')) {
            loadMemoryBtn.querySelector('span').textContent = '加载记忆';
        } else {
            loadMemoryBtn.textContent = '加载记忆';
        }
    } finally {
        loadMemoryBtn.disabled = false;
    }
}

// 保存用户长期记忆
async function saveUserMemory() {
    if (!saveMemoryBtn || !memoryTextarea) return;
    
    const memoryText = memoryTextarea.value.trim();
    
    // 构建请求体：value 需要是 JSON 格式
    const valueObj = {
        memory: memoryText
    };
    
    saveMemoryBtn.disabled = true;
    const saveBtnSpan = saveMemoryBtn.querySelector('span');
    if (saveBtnSpan) {
        saveBtnSpan.textContent = '保存中...';
    } else {
        saveMemoryBtn.textContent = '保存中...';
    }
    
    try {
        const response = await fetch(`${API_BASE}/profile/store`, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                value: valueObj
            }),
        });
        
        if (response.ok) {
            // 更新最后更新时间
            if (memoryMeta) {
                memoryMeta.innerHTML = `<div class="memory-updated"><svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/><polyline points="12 6 12 12 16 14" stroke="currentColor" stroke-width="2"/></svg>最后更新：${formatDateTime(new Date().toISOString())}</div>`;
            }
            if (saveBtnSpan) {
                saveBtnSpan.textContent = '保存';
            } else {
                saveMemoryBtn.textContent = '保存';
            }
            // 显示成功提示（使用更友好的方式）
            showToast('长期记忆保存成功', 'success');
        } else {
            const error = await response.json().catch(() => ({}));
            alert(error.error || '保存长期记忆失败');
            if (saveBtnSpan) {
                saveBtnSpan.textContent = '保存';
            } else {
                saveMemoryBtn.textContent = '保存';
            }
        }
    } catch (error) {
        console.error('Failed to save user memory:', error);
        alert('保存长期记忆失败，请稍后重试');
        if (saveBtnSpan) {
            saveBtnSpan.textContent = '保存';
        } else {
            saveMemoryBtn.textContent = '保存';
        }
    } finally {
        saveMemoryBtn.disabled = false;
    }
}

// 删除用户长期记忆
async function deleteUserMemory() {
    if (!deleteMemoryBtn) return;
    
    const confirmDelete = window.confirm('确定要删除长期记忆吗？此操作不可恢复。');
    if (!confirmDelete) return;
    
    deleteMemoryBtn.disabled = true;
    const deleteBtnSpan = deleteMemoryBtn.querySelector('span');
    if (deleteBtnSpan) {
        deleteBtnSpan.textContent = '删除中...';
    } else {
        deleteMemoryBtn.textContent = '删除中...';
    }
    
    try {
        const response = await fetch(`${API_BASE}/profile/store`, {
            method: 'DELETE',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
            },
        });
        
        if (response.ok) {
            // 清空显示
            if (memoryTextarea) {
                memoryTextarea.value = '';
            }
            if (memoryMeta) {
                memoryMeta.innerHTML = '<div class="memory-empty"><svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/><line x1="12" y1="8" x2="12" y2="12" stroke="currentColor" stroke-width="2"/><line x1="12" y1="16" x2="12.01" y2="16" stroke="currentColor" stroke-width="2"/></svg>暂无长期记忆数据</div>';
            }
            if (deleteBtnSpan) {
                deleteBtnSpan.textContent = '删除';
            } else {
                deleteMemoryBtn.textContent = '删除';
            }
            showToast('长期记忆删除成功', 'success');
        } else {
            const error = await response.json().catch(() => ({}));
            alert(error.error || '删除长期记忆失败');
            if (deleteBtnSpan) {
                deleteBtnSpan.textContent = '删除';
            } else {
                deleteMemoryBtn.textContent = '删除';
            }
        }
    } catch (error) {
        console.error('Failed to delete user memory:', error);
        alert('删除长期记忆失败，请稍后重试');
        if (deleteBtnSpan) {
            deleteBtnSpan.textContent = '删除';
        } else {
            deleteMemoryBtn.textContent = '删除';
        }
    } finally {
        deleteMemoryBtn.disabled = false;
    }
}

// 显示提示消息
function showToast(message, type = 'info') {
    // 移除已存在的toast
    const existingToast = document.querySelector('.toast');
    if (existingToast) {
        existingToast.remove();
    }
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    // 触发动画
    setTimeout(() => {
        toast.classList.add('show');
    }, 10);
    
    // 3秒后自动移除
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 3000);
}

// 格式化日期时间
function formatDateTime(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day} ${hours}:${minutes}`;
}

// 工具函数
function formatTime(isoString) {
    if (!isoString) return '刚刚';
    
    // 处理可能的日期格式：ISO 8601 字符串或时间戳
    let date;
    if (typeof isoString === 'string') {
        date = new Date(isoString);
    } else if (typeof isoString === 'number') {
        date = new Date(isoString);
    } else {
        return '刚刚';
    }
    
    // 检查日期是否有效
    if (isNaN(date.getTime())) {
        return '刚刚';
    }
    
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

// 统一获取消息的 created_at 字段（兼容不同命名）
function getMessageCreatedAt(msg) {
    if (!msg) return '';
    return msg.created_at || msg.CreatedAt || msg.createdAt || '';
}

// 对 AI / 用户回复做简单格式化：换行 + 加粗（支持 **粗体**）
function formatMessageContent(text) {
    if (!text) return '';

    // 先做 HTML 转义，防止 XSS
    const escaped = escapeHtml(text);

    // 处理换行：\n -> <br>
    let html = escaped.replace(/\r\n|\r|\n/g, '<br>');

    // 处理简单粗体：**xxx** -> <strong>xxx</strong>
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    return html;
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

// 显示 AI 回复的加载动画（类似 ChatGPT）
function showLoadingMessage() {
    // 先移除可能存在的旧加载动画
    hideLoadingMessage();
    
    const loadingHtml = `
        <div class="message" id="loadingMessage">
            <div class="message-avatar">
                <svg viewBox="0 0 24 24" fill="none"><path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </div>
            <div class="message-content">
                <div class="message-text loading-text">
                    <span class="loading-dot"></span>
                    <span class="loading-dot"></span>
                    <span class="loading-dot"></span>
                </div>
            </div>
        </div>
    `;
    messagesList.insertAdjacentHTML('beforeend', loadingHtml);
    scrollToBottom();
}

// 隐藏加载动画
function hideLoadingMessage() {
    const loadingMsg = document.getElementById('loadingMessage');
    if (loadingMsg) {
        loadingMsg.remove();
    }
}
