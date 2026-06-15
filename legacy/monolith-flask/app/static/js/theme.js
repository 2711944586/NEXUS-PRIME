document.addEventListener('DOMContentLoaded', () => {
    // 1. 更新主题图标 (主题已在 head 中的内联脚本设置，这里只需更新图标)
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
    updateThemeIcon(currentTheme);

    // 2. 绑定切换按钮
    const themeToggleBtn = document.getElementById('theme-toggle');
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            toggleTheme();
        });
    }
    
    function toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        
        // 添加 theme-switching class 禁用所有过渡动画
        document.documentElement.classList.add('theme-switching');
        
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('nexus-theme', newTheme);
        updateThemeIcon(newTheme);
        
        // 延迟移除 theme-switching class 以恢复正常过渡
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                document.documentElement.classList.remove('theme-switching');
            });
        });
        
        // 更新粒子颜色
        if(window.pJSDom && window.pJSDom.length) {
            const particleColor = newTheme === 'dark' ? '#6366f1' : '#8b5cf6';
            window.pJSDom[0].pJS.particles.color.value = particleColor;
            window.pJSDom[0].pJS.particles.line_linked.color = particleColor;
            window.pJSDom[0].pJS.fn.particlesRefresh();
        }
        
        showToast(`已切换到${newTheme === 'dark' ? '夜间' : '日间'}模式`, 'info');
    }
    
    function updateThemeIcon(theme) {
        const btn = document.getElementById('theme-toggle');
        if (btn) {
            const icon = btn.querySelector('i');
            if (theme === 'dark') {
                icon.className = 'fas fa-sun';
                btn.title = '切换到日间模式';
            } else {
                icon.className = 'fas fa-moon';
                btn.title = '切换到夜间模式';
            }
        }
    }

    // 3. 显示 Flash 消息
    const flashData = document.querySelectorAll('.flash-data');
    flashData.forEach(flash => {
        const category = flash.dataset.category;
        const message = flash.dataset.message;
        showToast(message, category);
    });
    
    // 4. 全局快捷键支持
    initKeyboardShortcuts();
    
    // 5. 搜索功能初始化
    initGlobalSearch();
    
    // 6. 初始化键盘帮助面板
    initHelpPanel();
    
    function initKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // 忽略输入框中的按键
            if (e.target.matches('input, textarea, select, [contenteditable]')) {
                // 仅响应 Escape 键
                if (e.key === 'Escape') {
                    e.target.blur();
                    closeAllModals();
                }
                return;
            }
            
            // Ctrl/Cmd + K: 打开全局搜索
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                openGlobalSearch();
                return;
            }
            
            // Escape: 关闭弹窗
            if (e.key === 'Escape') {
                closeAllModals();
                return;
            }
            
            // Alt + 数字键导航
            if (e.altKey && e.key >= '1' && e.key <= '9') {
                e.preventDefault();
                const navItems = document.querySelectorAll('.sidebar-nav > .nav-item');
                const index = parseInt(e.key) - 1;
                if (navItems[index]) {
                    navItems[index].click();
                }
                return;
            }
            
            // ? 显示帮助
            if (e.key === '?') {
                e.preventDefault();
                toggleHelpPanel();
                return;
            }
            
            // G 系列快捷键 (Go to)
            if (e.key === 'g') {
                window._waitingForG = true;
                setTimeout(() => { window._waitingForG = false; }, 500);
                return;
            }
            
            if (window._waitingForG) {
                window._waitingForG = false;
                e.preventDefault();
                
                const shortcuts = {
                    'd': '/dashboard',
                    'i': '/inventory',
                    's': '/sales/kanban',
                    'n': '/cms/news',
                    'a': '/ai/chat',
                    'p': '/profile',
                    'h': '/'
                };
                
                if (shortcuts[e.key]) {
                    window.location.href = shortcuts[e.key];
                }
                return;
            }
            
            // T: 切换主题
            if (e.key === 't' || e.key === 'T') {
                toggleTheme();
                return;
            }
            
            // N: 新建 (在对应页面)
            if (e.key === 'n' && !e.ctrlKey && !e.metaKey) {
                const newButtons = document.querySelector('[data-action="new"], .btn-primary[href*="new"], .btn-primary[href*="create"], .btn-primary[href*="editor"]');
                if (newButtons) {
                    newButtons.click();
                }
                return;
            }
        });
    }
    
    function initGlobalSearch() {
        // 创建搜索模态框
        const searchModal = document.createElement('div');
        searchModal.id = 'global-search-modal';
        searchModal.className = 'search-modal';
        searchModal.innerHTML = `
            <div class="search-modal-content">
                <div class="search-header">
                    <i class="fas fa-search"></i>
                    <input type="text" id="global-search-input" placeholder="搜索页面、功能或操作... (按 Ctrl+K 打开)" autocomplete="off">
                    <span class="search-shortcut">ESC</span>
                </div>
                <div class="search-results" id="search-results">
                    <div class="search-section">
                        <div class="search-section-title">快速导航</div>
                        <div class="search-items">
                            <a href="/dashboard" class="search-item">
                                <i class="fas fa-chart-pie"></i>
                                <span>指挥舱 Dashboard</span>
                            </a>
                            <a href="/inventory" class="search-item">
                                <i class="fas fa-box"></i>
                                <span>量子仓储 WMS</span>
                            </a>
                            <a href="/sales/kanban" class="search-item">
                                <i class="fas fa-file-invoice"></i>
                                <span>商业订单 CRM</span>
                            </a>
                            <a href="/cms/news" class="search-item">
                                <i class="fas fa-rss"></i>
                                <span>资讯中心 CMS</span>
                            </a>
                            <a href="/ai/chat" class="search-item">
                                <i class="fas fa-robot"></i>
                                <span>AI 智脑</span>
                            </a>
                            <a href="/reports" class="search-item">
                                <i class="fas fa-chart-bar"></i>
                                <span>数据分析</span>
                            </a>
                            <a href="/profile" class="search-item">
                                <i class="fas fa-user-circle"></i>
                                <span>个人中心</span>
                            </a>
                            <a href="/system/settings" class="search-item">
                                <i class="fas fa-cog"></i>
                                <span>系统设置</span>
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(searchModal);
        
        // 搜索输入处理
        const searchInput = document.getElementById('global-search-input');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                filterSearchResults(e.target.value);
            });
            
            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    const firstResult = document.querySelector('.search-item:not([style*="display: none"])');
                    if (firstResult) {
                        firstResult.click();
                    }
                }
            });
        }
        
        // 点击背景关闭
        searchModal.addEventListener('click', (e) => {
            if (e.target === searchModal) {
                closeGlobalSearch();
            }
        });
    }
    
    function filterSearchResults(query) {
        const items = document.querySelectorAll('.search-item');
        const lowerQuery = query.toLowerCase();
        
        items.forEach(item => {
            const text = item.textContent.toLowerCase();
            if (text.includes(lowerQuery) || lowerQuery === '') {
                item.style.display = 'flex';
            } else {
                item.style.display = 'none';
            }
        });
    }
    
    function initHelpPanel() {
        const helpPanel = document.createElement('div');
        helpPanel.id = 'help-panel';
        helpPanel.className = 'help-panel';
        helpPanel.innerHTML = `
            <div class="help-panel-content">
                <div class="help-header">
                    <h3><i class="fas fa-keyboard me-2"></i>键盘快捷键</h3>
                    <button class="help-close" onclick="toggleHelpPanel()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="help-body">
                    <div class="shortcut-group">
                        <div class="shortcut-title">全局操作</div>
                        <div class="shortcut-item">
                            <span class="shortcut-keys"><kbd>Ctrl</kbd><kbd>K</kbd></span>
                            <span class="shortcut-desc">打开快速搜索</span>
                        </div>
                        <div class="shortcut-item">
                            <span class="shortcut-keys"><kbd>T</kbd></span>
                            <span class="shortcut-desc">切换深色/浅色主题</span>
                        </div>
                        <div class="shortcut-item">
                            <span class="shortcut-keys"><kbd>?</kbd></span>
                            <span class="shortcut-desc">显示/隐藏此帮助</span>
                        </div>
                        <div class="shortcut-item">
                            <span class="shortcut-keys"><kbd>Esc</kbd></span>
                            <span class="shortcut-desc">关闭弹窗/取消操作</span>
                        </div>
                    </div>
                    <div class="shortcut-group">
                        <div class="shortcut-title">导航快捷键 (先按 G)</div>
                        <div class="shortcut-item">
                            <span class="shortcut-keys"><kbd>G</kbd><kbd>D</kbd></span>
                            <span class="shortcut-desc">前往 Dashboard</span>
                        </div>
                        <div class="shortcut-item">
                            <span class="shortcut-keys"><kbd>G</kbd><kbd>I</kbd></span>
                            <span class="shortcut-desc">前往库存管理</span>
                        </div>
                        <div class="shortcut-item">
                            <span class="shortcut-keys"><kbd>G</kbd><kbd>S</kbd></span>
                            <span class="shortcut-desc">前往销售订单</span>
                        </div>
                        <div class="shortcut-item">
                            <span class="shortcut-keys"><kbd>G</kbd><kbd>A</kbd></span>
                            <span class="shortcut-desc">前往 AI 助手</span>
                        </div>
                        <div class="shortcut-item">
                            <span class="shortcut-keys"><kbd>G</kbd><kbd>P</kbd></span>
                            <span class="shortcut-desc">前往个人中心</span>
                        </div>
                    </div>
                    <div class="shortcut-group">
                        <div class="shortcut-title">侧边栏快速访问</div>
                        <div class="shortcut-item">
                            <span class="shortcut-keys"><kbd>Alt</kbd><kbd>1-9</kbd></span>
                            <span class="shortcut-desc">跳转到对应菜单项</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(helpPanel);
        
        // 点击背景关闭
        helpPanel.addEventListener('click', (e) => {
            if (e.target === helpPanel) {
                toggleHelpPanel();
            }
        });
    }
});

// 全局函数
function openGlobalSearch() {
    const modal = document.getElementById('global-search-modal');
    if (modal) {
        modal.classList.add('open');
        const input = document.getElementById('global-search-input');
        if (input) {
            input.value = '';
            input.focus();
            filterSearchResults('');
        }
    }
}

function closeGlobalSearch() {
    const modal = document.getElementById('global-search-modal');
    if (modal) {
        modal.classList.remove('open');
    }
}

function toggleHelpPanel() {
    const panel = document.getElementById('help-panel');
    if (panel) {
        panel.classList.toggle('open');
    }
}

function closeAllModals() {
    closeGlobalSearch();
    const helpPanel = document.getElementById('help-panel');
    if (helpPanel) helpPanel.classList.remove('open');
    
    // 关闭其他可能的模态框
    document.querySelectorAll('.modal-overlay.open, .modal.show').forEach(m => {
        m.classList.remove('open', 'show');
    });
}

function filterSearchResults(query) {
    const items = document.querySelectorAll('.search-item');
    const lowerQuery = query.toLowerCase();
    
    items.forEach(item => {
        const text = item.textContent.toLowerCase();
        if (text.includes(lowerQuery) || lowerQuery === '') {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });
}

// Toast 通知函数
function showToast(message, category = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${category}`;
    
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        danger: 'fa-exclamation-triangle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };
    
    const icon = icons[category] || icons.info;
    
    toast.innerHTML = `
        <i class="fas ${icon}"></i>
        <span>${message}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    container.appendChild(toast);
    
    // 添加显示动画
    setTimeout(() => toast.classList.add('show'), 10);
    
    // 3秒后自动移除
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}