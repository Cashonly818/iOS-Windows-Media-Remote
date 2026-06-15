/**
 * PC Media Remote - 前端主逻辑
 * 功能: PIN验证 / 局域网扫描 / WebSocket实时同步 / 全功能遥控
 */

// ================================================================
//  状态管理
// ================================================================
const STATE = {
    serverUrl: '',          // 当前服务器地址 (如 http://192.168.1.100:8080)
    token: '',              // 认证 token
    ws: null,               // WebSocket 连接
    wsConnected: false,     // WebSocket 连接状态
    pollTimer: null,        // HTTP 轮询定时器
    currentSong: {},        // 当前歌曲信息
    currentVolume: 50,      // 当前音量
    isMuted: false,         // 静音状态
    isPlaying: false,       // 播放状态
    currentSpeed: 1.0,      // 当前倍速
};

// ================================================================
//  DOM 缓存
// ================================================================
const $ = (id) => document.getElementById(id);

const DOM = {
    headerBar: $('header-bar'),
    statusDot: $('status-dot'),
    pcNameDisplay: $('pc-name-display'),
    clockDisplay: $('clock-display'),

    pinSection: $('pin-section'),
    pinInput: $('pin-input'),
    pinSubmit: $('pin-submit-btn'),
    pinError: $('pin-error'),

    connectSection: $('connect-section'),
    scanBtn: $('scan-btn'),
    scanStatus: $('scan-status'),
    foundServers: $('found-servers'),
    ipInput: $('ip-input'),
    connectBtn: $('connect-btn'),
    savedIpHint: $('saved-ip-hint'),
    useSavedIp: $('use-saved-ip'),

    remoteSection: $('remote-section'),

    songCover: $('song-cover'),
    coverPlaceholder: document.querySelector('.cover-placeholder'),
    coverImg: $('cover-img'),
    songTitle: $('song-title'),
    songArtist: $('song-artist'),
    songSource: $('song-source'),
    songStatus: $('song-status'),

    progressBar: $('progress-bar'),
    timeCurrent: $('time-current'),
    timeTotal: $('time-total'),

    btnPlayPause: $('btn-playpause'),
    btnPrevious: $('btn-previous'),
    btnNext: $('btn-next'),

    volumeSlider: $('volume-slider'),
    volumePercent: $('volume-percent'),
    btnVolUp: $('btn-vol-up'),
    btnVolDown: $('btn-vol-down'),
    btnMute: $('btn-mute'),
    muteIcon: $('mute-icon'),

    btnFullscreen: $('btn-fullscreen'),
    btnForward: $('btn-forward'),
    btnBackward: $('btn-backward'),

    btnLock: $('btn-lock'),
    btnSleep: $('btn-sleep'),
    btnShutdown: $('btn-shutdown'),
    btnRestart: $('btn-restart'),

    confirmDialog: $('confirm-dialog'),
    confirmMsg: $('confirm-msg'),
    confirmCancel: $('confirm-cancel'),
    confirmOk: $('confirm-ok'),

    toast: $('toast'),
};

// ================================================================
//  初始化
// ================================================================
document.addEventListener('DOMContentLoaded', () => {
    initClock();
    loadSavedConfig();
    loadQRCode();
    bindEvents();
    registerServiceWorker();

    // 智能连接判断:
    // 1. 扫码打开 http://192.168.x.x:8080 → 自动连接当前服务器
    // 2. 有历史记录 + token → 尝试自动重连
    // 3. 其他 → 显示连接界面
    const currentOrigin = window.location.origin;  // 如 http://192.168.5.12:8080

    if (STATE.serverUrl && STATE.token) {
        // 有历史记录：尝试重连
        tryAutoConnect();
    } else if (currentOrigin.startsWith('http://192.168.') ||
               currentOrigin.startsWith('http://10.') ||
               currentOrigin.startsWith('http://172.')) {
        // 扫码或直接输入 IP 打开的：自动使用当前地址作为服务器
        STATE.serverUrl = currentOrigin;
        saveConfig();
        // 检查是否需要 PIN
        checkPinAndConnect();
    } else {
        showConnectUI();
    }
});

// 检查 PIN 状态后决定直接进入遥控还是显示 PIN 输入
async function checkPinAndConnect() {
    try {
        const resp = await fetch(STATE.serverUrl + '/api/auth/status');
        const data = await resp.json();
        if (data.pin_required && !STATE.token) {
            // 需要 PIN 且没有 token
            showPinUI();
        } else {
            showRemoteUI();
        }
    } catch (e) {
        showConnectUI();
    }
}

// ================================================================
//  时钟更新
// ================================================================
function initClock() {
    updateClock();
    setInterval(updateClock, 10000);
}

function updateClock() {
    const now = new Date();
    DOM.clockDisplay.textContent =
        now.getHours().toString().padStart(2, '0') + ':' +
        now.getMinutes().toString().padStart(2, '0');
}

// ================================================================
//  本地存储
// ================================================================
function loadSavedConfig() {
    try {
        STATE.serverUrl = localStorage.getItem('pc_remote_url') || '';
        STATE.token = localStorage.getItem('pc_remote_token') || '';
        const savedIp = STATE.serverUrl.replace(/^https?:\/\//, '').replace(/\/$/, '');
        if (savedIp) {
            DOM.savedIpHint.classList.remove('hidden');
            DOM.useSavedIp.textContent = savedIp;
            DOM.useSavedIp.href = '#';
        }
    } catch (e) { /* localStorage 不可用 */ }
}

function saveConfig() {
    try {
        if (STATE.serverUrl) localStorage.setItem('pc_remote_url', STATE.serverUrl);
        if (STATE.token) localStorage.setItem('pc_remote_token', STATE.token);
    } catch (e) { /* 忽略 */ }
}

function clearConfig() {
    try {
        localStorage.removeItem('pc_remote_url');
        localStorage.removeItem('pc_remote_token');
    } catch (e) { /* 忽略 */ }
}

// ================================================================
//  事件绑定
// ================================================================
function bindEvents() {
    // PIN
    DOM.pinSubmit.addEventListener('click', handlePinSubmit);
    DOM.pinInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') handlePinSubmit();
    });

    // 扫描 & 连接
    DOM.scanBtn.addEventListener('click', scanLAN);
    DOM.connectBtn.addEventListener('click', () => connectToServer(DOM.ipInput.value.trim()));
    DOM.ipInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') connectToServer(DOM.ipInput.value.trim());
    });
    DOM.useSavedIp.addEventListener('click', (e) => {
        e.preventDefault();
        if (STATE.serverUrl) connectToServer(STATE.serverUrl.replace(/^https?:\/\//, ''));
    });

    // 播放控制 — 即时切换 + 动画
    DOM.btnPlayPause.addEventListener('click', () => {
        STATE.isPlaying = !STATE.isPlaying;
        const btn = DOM.btnPlayPause;
        const target = btn.querySelector('span') || btn;
        target.textContent = STATE.isPlaying ? '⏸' : '▶';
        if (STATE.isPlaying) {
            btn.classList.add('is-playing');
        } else {
            btn.classList.remove('is-playing');
        }
        btn.style.transform = 'scale(0.88)';
        setTimeout(() => { btn.style.transform = ''; }, 150);
        updateHeaderDot();
        apiPost('/api/playpause');
    });
    DOM.btnPrevious.addEventListener('click', () => apiPost('/api/previous'));
    DOM.btnNext.addEventListener('click', () => apiPost('/api/next'));

    // 进度条
    DOM.progressBar.addEventListener('input', () => {
        const pct = parseInt(DOM.progressBar.value);
        const duration = STATE.currentSong.duration || 0;
        if (duration > 0) {
            DOM.timeCurrent.textContent = formatTime(duration * pct / 100);
        }
    });
    DOM.progressBar.addEventListener('change', () => {
        const pct = parseInt(DOM.progressBar.value);
        const duration = STATE.currentSong.duration || 0;
        if (duration > 0) {
            const targetSec = Math.round(duration * pct / 100);
            apiPost('/api/seek', { position: targetSec });
        }
    });

    // 音量
    DOM.btnVolUp.addEventListener('click', () => apiPost('/api/volumeup'));
    DOM.btnVolDown.addEventListener('click', () => apiPost('/api/volumedown'));
    DOM.volumeSlider.addEventListener('input', () => {
        const vol = parseInt(DOM.volumeSlider.value);
        DOM.volumePercent.textContent = vol + '%';
    });
    DOM.volumeSlider.addEventListener('change', () => {
        const vol = parseInt(DOM.volumeSlider.value);
        apiPost('/api/volume', { level: vol });
    });
    DOM.btnMute.addEventListener('click', () => apiPost('/api/mute'));

    // PotPlayer
    DOM.btnFullscreen.addEventListener('click', () => apiPost('/api/fullscreen'));
    DOM.btnForward.addEventListener('click', () => apiPost('/api/seek/forward'));
    DOM.btnBackward.addEventListener('click', () => apiPost('/api/seek/backward'));

    // 倍速按钮
    document.querySelectorAll('.speed-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const speed = parseFloat(chip.dataset.speed);
            setPlaybackSpeed(speed);
        });
    });

    // 系统控制
    DOM.btnLock.addEventListener('click', () => apiPost('/api/lock'));
    DOM.btnSleep.addEventListener('click', () => apiPost('/api/sleep'));
    DOM.btnShutdown.addEventListener('click', () => showConfirm('确定要关机吗？电脑将在 60 秒后关闭。', () => {
        apiPost('/api/shutdown', { confirm: true });
    }));
    DOM.btnRestart.addEventListener('click', () => showConfirm('确定要重启吗？电脑将在 60 秒后重启。', () => {
        apiPost('/api/restart', { confirm: true });
    }));

    // 确认对话框
    DOM.confirmCancel.addEventListener('click', hideConfirm);
    DOM.confirmDialog.addEventListener('click', (e) => {
        if (e.target === DOM.confirmDialog) hideConfirm();
    });

    // Toast 点击关闭
    DOM.toast.addEventListener('click', () => DOM.toast.classList.add('hidden'));
}

// ================================================================
//  UI 切换
// ================================================================
function showConnectUI() {
    DOM.remoteSection.classList.add('hidden');
    DOM.pinSection.classList.add('hidden');
    DOM.connectSection.classList.remove('hidden');
    DOM.statusDot.className = 'header-dot disconnected';
    DOM.pcNameDisplay.textContent = '未连接';
    disconnectWebSocket();
    stopPolling();
}

function showRemoteUI() {
    DOM.connectSection.classList.add('hidden');
    DOM.pinSection.classList.add('hidden');
    DOM.remoteSection.classList.remove('hidden');
    DOM.statusDot.className = 'header-dot connected';
    connectWebSocket();
    startPolling();
}

function showPinUI() {
    DOM.connectSection.classList.add('hidden');
    DOM.remoteSection.classList.add('hidden');
    DOM.pinSection.classList.remove('hidden');
    DOM.pinInput.value = '';
    DOM.pinError.classList.add('hidden');
    setTimeout(() => DOM.pinInput.focus(), 300);
}

// ================================================================
//  PIN 验证
// ================================================================
async function handlePinSubmit() {
    const pin = DOM.pinInput.value.trim();
    if (pin.length !== 4 || !/^\d+$/.test(pin)) {
        DOM.pinError.textContent = '请输入 4 位数字';
        DOM.pinError.classList.remove('hidden');
        return;
    }

    DOM.pinSubmit.disabled = true;
    try {
        const resp = await fetch(STATE.serverUrl + '/api/auth', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pin: pin }),
        });
        const data = await resp.json();
        if (data.ok && data.token) {
            STATE.token = data.token;
            saveConfig();
            showToast('✅ 验证成功');
            showRemoteUI();
        } else {
            DOM.pinError.textContent = data.error || 'PIN 码错误';
            DOM.pinError.classList.remove('hidden');
            DOM.pinInput.value = '';
            DOM.pinInput.focus();
        }
    } catch (e) {
        DOM.pinError.textContent = '连接失败，请检查网络';
        DOM.pinError.classList.remove('hidden');
    }
    DOM.pinSubmit.disabled = false;
}

async function checkPinRequired() {
    try {
        const resp = await fetch(STATE.serverUrl + '/api/auth/status');
        const data = await resp.json();
        return data.pin_required === true;
    } catch (e) { return false; }
}

// ================================================================
//  连接管理
// ================================================================
async function connectToServer(addr) {
    addr = addr.replace(/^https?:\/\//, '').replace(/\/$/, '');
    if (!addr) {
        showToast('请输入 IP 地址');
        return;
    }

    // 自动补全端口
    if (!addr.includes(':')) addr += ':8080';

    STATE.serverUrl = 'http://' + addr;
    DOM.connectBtn.disabled = true;
    DOM.connectBtn.textContent = '连接中...';

    try {
        // 先 ping 测试
        const resp = await fetch(STATE.serverUrl + '/api/ping', {
            signal: AbortSignal.timeout(5000),
        });
        const data = await resp.json();
        if (!data.ok) throw new Error('服务不可用');

        DOM.pcNameDisplay.textContent = data.pc_name || 'PC';
        saveConfig();

        // 检查是否需要 PIN
        if (data.has_pin) {
            showPinUI();
        } else {
            STATE.token = '';
            showRemoteUI();
        }

        showToast('已连接到 ' + (data.pc_name || addr));
    } catch (e) {
        showToast('连接失败: ' + (e.message || '无法访问服务器'));
        DOM.pcNameDisplay.textContent = '未连接';
        DOM.statusDot.className = 'header-dot disconnected';
    }

    DOM.connectBtn.disabled = false;
    DOM.connectBtn.textContent = '连接';
}

async function tryAutoConnect() {
    DOM.connectBtn.textContent = '自动连接中...';
    DOM.connectBtn.disabled = true;

    try {
        const resp = await fetch(STATE.serverUrl + '/api/ping', {
            headers: STATE.token ? { 'X-Auth-Token': STATE.token } : {},
            signal: AbortSignal.timeout(5000),
        });
        const data = await resp.json();
        if (!data.ok) throw new Error('fail');

        DOM.pcNameDisplay.textContent = data.pc_name || 'PC';

        if (data.has_pin && !STATE.token) {
            showPinUI();
        } else if (data.has_pin && STATE.token) {
            // 尝试用保存的 token
            const statusResp = await fetch(STATE.serverUrl + '/api/status', {
                headers: { 'X-Auth-Token': STATE.token },
                signal: AbortSignal.timeout(3000),
            });
            if (statusResp.ok) {
                showRemoteUI();
            } else {
                showPinUI();
            }
        } else {
            showRemoteUI();
        }
    } catch (e) {
        showConnectUI();
        showToast('自动连接失败，请检查电脑是否开机');
    }

    DOM.connectBtn.disabled = false;
    DOM.connectBtn.textContent = '连接';
}

// ================================================================
//  二维码扫码连接
// ================================================================
async function loadQRCode() {
    // 从服务器获取二维码 URL
    try {
        const resp = await fetch('/api/qrcode');
        const data = await resp.json();
        if (data.ok && data.url) {
            document.getElementById('qrcode-url-text').textContent = data.url;
            // 如果没有二维码图片,隐藏图片元素
            if (!data.qrcode_base64) {
                document.getElementById('qrcode-img').style.display = 'none';
            }
        }
    } catch (e) {
        // 页面可能还没连上服务器,稍后再试
        console.log('[QR] 等待服务器连接...');
    }
}

function toggleQRCode() {
    const container = document.getElementById('qrcode-container');
    const btn = document.getElementById('qrcode-btn');
    if (container.classList.contains('hidden')) {
        container.classList.remove('hidden');
        btn.querySelector('span:last-child').textContent = '隐藏二维码';
        // 重新加载 (页面刚加载时可能还没连上)
        loadQRCode();
    } else {
        container.classList.add('hidden');
        btn.querySelector('span:last-child').textContent = '扫码连接 (推荐)';
    }
}

// ================================================================
//  局域网扫描
// ================================================================
async function scanLAN() {
    DOM.scanBtn.disabled = true;
    DOM.scanStatus.textContent = '正在扫描...';
    DOM.foundServers.innerHTML = '';

    // 覆盖常见路由器网段 (小米/华硕/TP-Link/光猫/企业网)
    // 优先扫描常见 IP 范围 (路由器 DHCP 通常分配 .2-.200)
    const subnets = [
        '192.168.1', '192.168.0', '192.168.2',
        '192.168.3', '192.168.5', '192.168.8',
        '192.168.31',   // 小米路由器
        '192.168.50',   // 华硕路由器
        '192.168.100',  // 部分光猫
        '10.0.0',       // 企业网络
    ];
    const port = 8080;
    const found = [];

    // 生成 IP 列表: 常见 IP 优先 (快速命中)
    function buildIPList(subnet) {
        const ips = [];
        // 第一优先级: 路由器附近和常用静态 IP
        const priority = [1, 100, 101, 102, 103, 104, 105, 110, 120, 150, 200, 2, 3, 4, 5, 6, 7, 8, 9, 10];
        for (const host of priority) {
            ips.push(`${subnet}.${host}`);
        }
        // 第二优先级: 其余 IP
        for (let host = 1; host <= 254; host++) {
            if (!priority.includes(host)) {
                ips.push(`${subnet}.${host}`);
            }
        }
        return ips;
    }

    // 扫描：高并发 + 短超时
    const CONCURRENCY = 50;  // 50 个并发请求
    const TIMEOUT_MS = 400;  // 400ms 超时 (局域网足够)

    for (const subnet of subnets) {
        if (found.length >= 1) break;  // 找到 1 个就停

        const ipList = buildIPList(subnet);
        DOM.scanStatus.textContent = `扫描 ${subnet}.x ...`;

        // 分批并发
        for (let i = 0; i < ipList.length; i += CONCURRENCY) {
            if (found.length >= 1) break;
            const batch = ipList.slice(i, i + CONCURRENCY);
            const batchResults = await Promise.all(
                batch.map(ip => probeServerQuick(ip, port, TIMEOUT_MS))
            );
            for (const result of batchResults) {
                if (result) {
                    found.push(result);
                    if (found.length >= 1) break;
                }
            }
            DOM.scanStatus.textContent = `扫描 ${subnet}.x ... ${Math.min(i + CONCURRENCY, ipList.length)}/${ipList.length}`;
        }
    }

    if (found.length > 0) {
        // 去重
        const unique = [];
        const seen = new Set();
        for (const s of found) {
            const key = `${s.ip}:${s.port}`;
            if (!seen.has(key)) { seen.add(key); unique.push(s); }
        }
        DOM.scanStatus.textContent = `发现 ${unique.length} 台设备`;
        DOM.foundServers.innerHTML = unique.map(s => `
            <div class="server-item" onclick="connectToServer('${s.ip}:${s.port}')">
                <div>
                    <div class="srv-name">${s.name}</div>
                    <div class="srv-ip">${s.ip}:${s.port}</div>
                </div>
                <div style="color: var(--accent)">→</div>
            </div>
        `).join('');
    } else {
        DOM.scanStatus.textContent = '未发现设备，请确认同一 WiFi 并手动输入 IP';
    }

    DOM.scanBtn.disabled = false;
}

async function probeServerQuick(ip, port, timeoutMs) {
    try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), timeoutMs);
        const resp = await fetch(`http://${ip}:${port}/api/ping`, {
            signal: controller.signal,
            mode: 'cors',
        });
        clearTimeout(timer);
        if (resp.ok) {
            const data = await resp.json();
            if (data.ok && data.pc_name) {
                return { ip, port, name: data.pc_name };
            }
        }
    } catch (e) { /* 忽略超时和网络错误 */ }
    return null;
}

// ================================================================
//  WebSocket 实时同步
// ================================================================
function connectWebSocket() {
    disconnectWebSocket();
    const wsUrl = STATE.serverUrl.replace(/^http/, 'ws') + '/ws';
    try {
        STATE.ws = new WebSocket(wsUrl);
        STATE.ws.onopen = () => {
            console.log('[WS] 已连接');
            STATE.wsConnected = true;
            // 请求首次状态
            STATE.ws.send(JSON.stringify({ action: 'get_status' }));
            // 心跳 (每 30 秒)
            STATE.ws._heartbeat = setInterval(() => {
                if (STATE.ws && STATE.ws.readyState === WebSocket.OPEN) {
                    STATE.ws.send(JSON.stringify({ action: 'ping' }));
                }
            }, 30000);
        };
        STATE.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'status') {
                    updateUIFromStatus(data);
                }
            } catch (e) { /* 忽略解析错误 */ }
        };
        STATE.ws.onclose = () => {
            console.log('[WS] 断开');
            STATE.wsConnected = false;
            clearInterval(STATE.ws._heartbeat);
            // 3 秒后自动重连
            setTimeout(() => {
                if (STATE.serverUrl && !STATE.wsConnected) {
                    connectWebSocket();
                }
            }, 3000);
        };
        STATE.ws.onerror = () => {
            STATE.wsConnected = false;
        };
    } catch (e) {
        console.log('[WS] 创建失败:', e);
    }
}

function disconnectWebSocket() {
    if (STATE.ws) {
        clearInterval(STATE.ws._heartbeat);
        STATE.ws.onclose = null;  // 防止重连
        STATE.ws.close();
        STATE.ws = null;
        STATE.wsConnected = false;
    }
}

// ================================================================
//  HTTP 轮询 (WebSocket 的 fallback)
// ================================================================
function startPolling() {
    stopPolling();
    fetchStatus();  // 立即拉一次
    STATE.pollTimer = setInterval(fetchStatus, 2000);  // 每 2 秒轮询
}

function stopPolling() {
    if (STATE.pollTimer) {
        clearInterval(STATE.pollTimer);
        STATE.pollTimer = null;
    }
}

async function fetchStatus() {
    if (!STATE.serverUrl) return;
    try {
        const headers = {};
        if (STATE.token) headers['X-Auth-Token'] = STATE.token;
        const resp = await fetch(STATE.serverUrl + '/api/status', {
            headers,
            signal: AbortSignal.timeout(3000),
        });
        if (resp.status === 401) {
            // Token 过期，重新验证
            showPinUI();
            return;
        }
        if (!resp.ok) return;
        const data = await resp.json();
        if (data.ok) {
            updateUIFromStatus(data);
        }
    } catch (e) { /* 静默失败 */ }
}

// ================================================================
//  UI 更新
// ================================================================
function updateHeaderDot() {
    // 仅显示连接状态，不反映播放状态
    if (STATE.serverUrl) {
        DOM.statusDot.className = 'header-dot connected';
    } else {
        DOM.statusDot.className = 'header-dot disconnected';
    }
}

function updateUIFromStatus(data) {
    // 电脑名称
    if (data.pc_name) DOM.pcNameDisplay.textContent = data.pc_name;

    // 时间
    if (data.time) DOM.clockDisplay.textContent = data.time;

    // 音量
    if (data.volume !== undefined) {
        STATE.currentVolume = data.volume;
        STATE.isMuted = data.muted || false;
        DOM.volumeSlider.value = data.volume;
        DOM.volumePercent.textContent = data.volume + '%';
        DOM.muteIcon.textContent = data.muted ? '🔇' : '🔊';
    }

    // 播放状态 — 同步按钮图标 + 样式 + 状态灯
    if (data.playing !== undefined) {
        STATE.isPlaying = data.playing;
        const target = DOM.btnPlayPause.querySelector('span') || DOM.btnPlayPause;
        target.textContent = data.playing ? '⏸' : '▶';
        if (data.playing) {
            DOM.btnPlayPause.classList.add('is-playing');
        } else {
            DOM.btnPlayPause.classList.remove('is-playing');
        }
        updateHeaderDot();
    }

    // 歌曲信息
    if (data.song) {
        STATE.currentSong = data.song;
        updateSongUI(data.song);
    }

    // 连接状态
    if (!STATE.serverUrl && data.pc_name) {
        STATE.serverUrl = window.location.origin;
    }
    updateHeaderDot();
}

function updateSongUI(song) {
    DOM.songTitle.textContent = song.title || '未在播放';
    DOM.songArtist.textContent = song.artist || '';
    DOM.songSource.textContent = song.source || '';

    // 播放状态指示
    if (song.playing) {
        DOM.songStatus.textContent = '● 正在播放';
        DOM.songStatus.style.color = 'var(--success)';
    } else if (song.title) {
        DOM.songStatus.textContent = '▎▎ 已暂停';
        DOM.songStatus.style.color = 'var(--text-secondary)';
    } else {
        DOM.songStatus.textContent = '';
    }

    // 进度条 — 始终启用
    DOM.progressBar.disabled = false;
    DOM.progressBar.max = 100;
    const pos = song.position || 0;
    const dur = song.duration || 0;
    if (dur > 0) {
        DOM.progressBar.value = Math.min(100, (pos / dur) * 100);
        DOM.timeTotal.textContent = formatTime(dur);
    } else if (pos > 0) {
        // 时长未知: 假设 4 分钟歌曲, 显示进度在 0-50% 范围
        DOM.progressBar.value = Math.min(50, pos / 4);
        DOM.timeTotal.textContent = '--:--';
    } else {
        DOM.progressBar.value = 0;
        DOM.timeTotal.textContent = '--:--';
    }
    DOM.timeCurrent.textContent = formatTime(pos);
}

// ================================================================
//  PotPlayer 倍速控制
// ================================================================
function setPlaybackSpeed(speed) {
    STATE.currentSpeed = speed;

    // 更新按钮 UI
    document.querySelectorAll('.speed-chip').forEach(chip => {
        const chipSpeed = parseFloat(chip.dataset.speed);
        chip.classList.toggle('active', chipSpeed === speed);
    });

    apiPost('/api/speed', { speed: speed });
}

// ================================================================
//  API 请求封装
// ================================================================
async function apiPost(path, body = {}) {
    if (!STATE.serverUrl) {
        showToast('请先连接电脑');
        return;
    }
    try {
        const headers = { 'Content-Type': 'application/json' };
        if (STATE.token) headers['X-Auth-Token'] = STATE.token;

        const resp = await fetch(STATE.serverUrl + path, {
            method: 'POST',
            headers,
            body: JSON.stringify(body),
            signal: AbortSignal.timeout(5000),
        });

        if (resp.status === 401) {
            showPinUI();
            return;
        }

        const data = await resp.json();
        if (data.ok) {
            // 操作成功，触发即时状态刷新
            if (path.includes('volume') || path.includes('mute')) {
                fetchStatus();
            }
        } else {
            showToast('操作失败: ' + (data.error || '未知错误'));
        }
    } catch (e) {
        if (e.name === 'TimeoutError') {
            showToast('请求超时');
        } else {
            showToast('连接失败');
        }
    }
}

// ================================================================
//  确认对话框
// ================================================================
let confirmCallback = null;

function showConfirm(msg, callback) {
    DOM.confirmMsg.textContent = msg;
    DOM.confirmDialog.classList.remove('hidden');
    confirmCallback = callback;
    DOM.confirmOk.focus();
}

function hideConfirm() {
    DOM.confirmDialog.classList.add('hidden');
    confirmCallback = null;
}

DOM.confirmOk.addEventListener('click', () => {
    if (confirmCallback) confirmCallback();
    hideConfirm();
});

// ================================================================
//  Toast
// ================================================================
let toastTimer;

function showToast(msg) {
    DOM.toast.textContent = msg;
    DOM.toast.classList.remove('hidden');
    DOM.toast.classList.add('show');

    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
        DOM.toast.classList.remove('show');
        DOM.toast.classList.add('hidden');
    }, 2000);
}

// ================================================================
//  PWA / Service Worker
// ================================================================
function registerServiceWorker() {
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js')
            .then(reg => console.log('[PWA] SW registered:', reg.scope))
            .catch(err => console.log('[PWA] SW registration failed:', err));
    }
}

// 监听 PWA 安装事件
window.addEventListener('beforeinstallprompt', (e) => {
    // 保存事件以便稍后触发
    window._pwaInstallPrompt = e;
});

// ================================================================
//  工具函数
// ================================================================
function formatTime(seconds) {
    if (!seconds || seconds <= 0 || !isFinite(seconds)) return '00:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
}

// ================================================================
//  键盘快捷键 (调试用)
// ================================================================
document.addEventListener('keydown', (e) => {
    if (document.activeElement.tagName === 'INPUT') return;
    switch (e.key) {
        case ' ': e.preventDefault(); apiPost('/api/playpause'); break;
        case 'ArrowRight': e.preventDefault(); apiPost('/api/next'); break;
        case 'ArrowLeft': e.preventDefault(); apiPost('/api/previous'); break;
        case 'ArrowUp': e.preventDefault(); apiPost('/api/volumeup'); break;
        case 'ArrowDown': e.preventDefault(); apiPost('/api/volumedown'); break;
    }
});
