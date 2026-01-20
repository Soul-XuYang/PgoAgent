// API 基础路径
const API_BASE = '/api/v1';

// DOM 元素
const loginForm = document.getElementById('loginForm');
const registerForm = document.getElementById('registerForm');
const loginFormElement = document.getElementById('loginFormElement');
const registerFormElement = document.getElementById('registerFormElement');
const switchToRegister = document.getElementById('switchToRegister');
const switchToLogin = document.getElementById('switchToLogin');
const loginError = document.getElementById('loginError');
const registerError = document.getElementById('registerError');
const loginBtn = document.getElementById('loginBtn');
const registerBtn = document.getElementById('registerBtn');

// 切换表单显示
switchToRegister.addEventListener('click', (e) => {
    e.preventDefault();
    showRegisterForm();
});

switchToLogin.addEventListener('click', (e) => {
    e.preventDefault();
    showLoginForm();
});

function showLoginForm() {
    loginForm.classList.add('active');
    registerForm.classList.remove('active');
    clearErrors();
    loginFormElement.reset();
}

function showRegisterForm() {
    registerForm.classList.add('active');
    loginForm.classList.remove('active');
    clearErrors();
    registerFormElement.reset();
}

// 显示错误消息
function showError(element, message) {
    element.textContent = message;
    element.style.display = 'block';

    // 触发 shake 动画
    element.classList.remove('shake');
    // 强制重绘，让重复触发也生效
    void element.offsetWidth;
    element.classList.add('shake');
}


function clearErrors() {
    loginError.style.display = 'none';
    registerError.style.display = 'none';
}

// 设置按钮加载状态
function setButtonLoading(button, loading) {
    const btnText = button.querySelector('.btn-text');
    const btnLoading = button.querySelector('.btn-loading');
    
    if (loading) {
        button.disabled = true;
        btnText.style.display = 'none';
        btnLoading.style.display = 'inline-block';
    } else {
        button.disabled = false;
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
    }
}

// 登录表单提交
loginFormElement.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearErrors();
    
    const formData = {
        username: document.getElementById('loginUsername').value.trim(),
        password: document.getElementById('loginPassword').value
    };
    
    if (!formData.username || !formData.password) {
        showError(loginError, '请输入用户名和密码');
        return;
    }
    
    setButtonLoading(loginBtn, true);
    
    try {
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData),
            credentials: 'include' // 允许携带 Cookie
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // 登录成功，跳转到聊天页面
            window.location.href = '/chat';
        } else {
            showError(loginError, data.error || '登录失败，请检查用户名和密码');
        }
    } catch (error) {
        console.error('Login error:', error);
        showError(loginError, '网络错误，请稍后重试');
    } finally {
        setButtonLoading(loginBtn, false);
    }
});

// 注册表单提交
registerFormElement.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearErrors();
    
    const password = document.getElementById('registerPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    
    if (password !== confirmPassword) {
        showError(registerError, '两次输入的密码不一致');
        return;
    }
    
    const formData = {
        username: document.getElementById('registerUsername').value.trim(),
        password: password
    };
    
    // 验证用户名格式（仅字母和数字）
    if (!/^[A-Za-z0-9]+$/.test(formData.username)) {
        showError(registerError, '用户名只能包含字母和数字');
        return;
    }
    
    if (formData.username.length < 3 || formData.username.length > 32) {
        showError(registerError, '用户名长度必须在3-32个字符之间');
        return;
    }
    
    if (password.length < 6 || password.length > 64) {
        showError(registerError, '密码长度必须在6-64个字符之间');
        return;
    }
    
    setButtonLoading(registerBtn, true);
    
    try {
        const response = await fetch(`${API_BASE}/auth/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData),
            credentials: 'include' // 允许携带 Cookie
        });
        
        const data = await response.json();
        
        if (response.ok || response.status === 201) {
            // 注册成功，自动登录并跳转
            showError(registerError, '注册成功！正在跳转...');
            setTimeout(() => {
                const resultUrl = '/chat';
                window.location.href = resultUrl;
            }, 1000);
        } else {
            showError(registerError, data.error || '注册失败，请稍后重试');
        }
    } catch (error) {
        console.error('Register error:', error);
        showError(registerError, '网络错误，请稍后重试');
    } finally {
        setButtonLoading(registerBtn, false);
    }
});

// 确认密码实时验证
document.getElementById('confirmPassword').addEventListener('blur', function() {
    const password = document.getElementById('registerPassword').value;
    const confirmPassword = this.value;
    
    if (confirmPassword && password !== confirmPassword) {
        this.setCustomValidity('两次输入的密码不一致');
        this.style.borderColor = '#ef4444';
    } else {
        this.setCustomValidity('');
        this.style.borderColor = '';
    }
});

// 用户名格式实时验证
document.getElementById('registerUsername').addEventListener('input', function() {
    const value = this.value;
    if (value && !/^[A-Za-z0-9]*$/.test(value)) {
        this.setCustomValidity('用户名只能包含字母和数字');
        this.style.borderColor = '#ef4444';
    } else {
        this.setCustomValidity('');
        this.style.borderColor = '';
    }
});
