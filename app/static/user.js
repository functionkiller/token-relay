const API = '';
let page = 1;

function toast(msg, ok = true) {
    const t = document.createElement('div');
    t.className = 'toast ' + (ok ? 'toast-ok' : 'toast-err');
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 3000);
}

function formatCredits(c) { return ((c || 0) / 100).toFixed(2); }
function formatNum(n) { return (n || 0).toLocaleString(); }

async function api(path, opts = {}) {
    const res = await fetch(path, { credentials: 'include', ...opts });
    if (res.status === 401) { window.location.href = '/login'; throw new Error('Unauthorized'); }
    return res;
}

function logout() {
    document.cookie = 'token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
    window.location.href = '/login';
}

// Highlight active nav link
(function() {
    const path = window.location.pathname;
    document.querySelectorAll('nav a').forEach(a => {
        if (a.getAttribute('href') === path) a.classList.add('active');
        else if (path.startsWith('/dashboard/') && a.getAttribute('href').startsWith('/dashboard/') && path.indexOf(a.getAttribute('href')) === 0) a.classList.add('active');
    });
})();

// Load user info
(async function loadNav() {
    try {
        const r = await api('/api/users/me');
        const u = await r.json();
        document.getElementById('nav-email').textContent = u.email;
    } catch(e) {}
})();

// ====== DASHBOARD ======
async function loadDashboard() {
    try {
        const [uRes, kRes, sRes, lRes] = await Promise.all([
            api('/api/users/me'),
            api('/api/users/me/keys'),
            api('/api/logs/stats'),
            api('/api/logs/usage?page=1&size=5')
        ]);
        const user = await uRes.json();
        const keys = await kRes.json();
        const stats = await sRes.json();
        const logs = await lRes.json();

        document.getElementById('balance').textContent = formatCredits(user.credit_balance);
        document.getElementById('keys-count').textContent = keys.length;
        document.getElementById('requests-today').textContent = formatNum(stats.total_requests);
        document.getElementById('tokens-today').textContent = formatNum(stats.total_tokens);

        const tbody = document.getElementById('recent-logs');
        if (logs.items.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="empty">No requests yet. Make your first API call!</td></tr>';
        } else {
            tbody.innerHTML = logs.items.map(l => `
                <tr>
                    <td>${new Date(l.created_at).toLocaleString()}</td>
                    <td>${l.model}</td>
                    <td>${formatNum(l.total_tokens)}</td>
                    <td>${formatCredits(l.credits_consumed)}</td>
                    <td><span class="badge ${l.status==='success'?'badge-ok':'badge-err'}">${l.status}</span></td>
                </tr>
            `).join('');
        }
    } catch(e) { console.error(e); }
}

// ====== MODELS ======
async function loadModels() {
    try {
        // Fetch public models list via v1 endpoint (needs API key, use admin list)
        const r = await api('/v1/public-models');
        const models = await r.json();
        const grid = document.getElementById('model-grid');
        if (models.length === 0) {
            grid.innerHTML = '<div class="empty" style="grid-column:1/-1;">No models available</div>';
            return;
        }
        grid.innerHTML = models.filter(m=>m.is_enabled).map(m => `
            <div class="model-card">
                <div class="provider">${m.provider.toUpperCase()}</div>
                <div class="model-name">${m.display_name}</div>
                <div class="pricing">
                    <div class="price-item">
                        <div class="price-val">$${((m.input_price||0)/100).toFixed(2)}</div>
                        <div class="price-lbl">Input / 1K tok</div>
                    </div>
                    <div class="price-item">
                        <div class="price-val">$${((m.output_price||0)/100).toFixed(2)}</div>
                        <div class="price-lbl">Output / 1K tok</div>
                    </div>
                </div>
                <div class="features">
                    ${m.supports_streaming ? '<span class="badge badge-ok">Streaming</span>' : ''}
                    ${m.supports_vision ? '<span class="badge badge-gray">Vision</span>' : ''}
                </div>
            </div>
        `).join('');
    } catch(e) { console.error(e); }
}

// ====== KEYS ======
async function loadKeys() {
    try {
        const r = await api('/api/users/me/keys');
        const keys = await r.json();
        const list = document.getElementById('keys-list');
        if (keys.length === 0) {
            list.innerHTML = '<div class="empty">No API keys yet. Create one above.</div>';
            return;
        }
        list.innerHTML = keys.map(k => `
            <div class="key-row">
                <div>
                    <span class="key-name">${k.name}</span>
                    <span class="key-meta">${k.key_prefix}... | Created ${new Date(k.created_at).toLocaleDateString()}</span>
                </div>
                <button class="danger" onclick="deleteKey('${k.id}')">Delete</button>
            </div>
        `).join('');
    } catch(e) {}
}

async function createKey() {
    const name = document.getElementById('key-name').value || 'default';
    try {
        const r = await api('/api/users/me/keys', {
            method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name})
        });
        const data = await r.json();
        document.getElementById('new-key').style.display = 'block';
        document.getElementById('full-key-display').textContent = data.full_key;
        document.getElementById('key-name').value = '';
        loadKeys();
    } catch(e) {}
}

function copyKey() {
    const key = document.getElementById('full-key-display').textContent;
    navigator.clipboard.writeText(key).then(() => toast('Key copied to clipboard'));
}

async function deleteKey(id) {
    if (!confirm('Delete this key? It will stop working immediately.')) return;
    await api(`/api/users/me/keys/${id}`, { method: 'DELETE' });
    loadKeys();
}

// ====== USAGE ======
async function loadUsage(p = 1) {
    page = p;
    try {
        const [sRes, lRes] = await Promise.all([
            api('/api/logs/stats'),
            api(`/api/logs/usage?page=${page}&size=15`)
        ]);
        const stats = await sRes.json();
        const data = await lRes.json();

        document.getElementById('s-requests').textContent = formatNum(stats.total_requests);
        document.getElementById('s-tokens').textContent = formatNum(stats.total_tokens);
        document.getElementById('s-credits').textContent = formatCredits(stats.total_credits);

        const tbody = document.getElementById('log-table');
        if (data.items.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="empty">No usage data yet</td></tr>';
        } else {
            tbody.innerHTML = data.items.map(l => `
                <tr>
                    <td>${new Date(l.created_at).toLocaleString()}</td>
                    <td>${l.model}</td>
                    <td>${l.provider}</td>
                    <td>${formatNum(l.prompt_tokens)}</td>
                    <td>${formatNum(l.completion_tokens)}</td>
                    <td>${formatCredits(l.credits_consumed)}</td>
                    <td>${l.latency_ms ? l.latency_ms+'ms' : '-'}</td>
                    <td><span class="badge ${l.status==='success'?'badge-ok':'badge-err'}">${l.status}</span></td>
                </tr>
            `).join('');
        }
        // Pagination
        let ph = '';
        for (let i = 1; i <= data.pages && i <= 10; i++) {
            ph += `<button onclick="loadUsage(${i})" class="${i===page?'active-page':''}">${i}</button>`;
        }
        document.getElementById('pager').innerHTML = ph;
    } catch(e) {}
}

// ====== BILLING ======
async function loadBilling(p = 1) {
    try {
        const [bRes, tRes] = await Promise.all([
            api('/api/billing/balance'),
            api(`/api/billing/transactions?page=${p}&size=15`)
        ]);
        const bal = await bRes.json();
        const data = await tRes.json();

        document.getElementById('balance').textContent = formatCredits(bal.credit_balance);

        const tbody = document.getElementById('txn-table');
        if (data.items.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="empty">No transactions yet</td></tr>';
        } else {
            tbody.innerHTML = data.items.map(t => {
                const typeBadge = {purchase:'badge-ok', consumption:'badge-err', refund:'badge-gray', admin_adjust:'badge-gray'}[t.type] || 'badge-gray';
                const sign = t.amount > 0 ? '+' : '';
                return `<tr>
                    <td>${new Date(t.created_at).toLocaleString()}</td>
                    <td><span class="badge ${typeBadge}">${t.type}</span></td>
                    <td>${sign}${formatCredits(Math.abs(t.amount))}</td>
                    <td>${formatCredits(t.balance_after)}</td>
                    <td>${t.note || '-'}</td>
                </tr>`;
            }).join('');
        }
        let ph = '';
        for (let i = 1; i <= data.pages && i <= 10; i++) {
            ph += `<button onclick="loadBilling(${i})" class="${i===p?'active-page':''}">${i}</button>`;
        }
        document.getElementById('txn-pager').innerHTML = ph;
    } catch(e) {}
}

// ====== SETTINGS ======
async function loadSettings() {
    try {
        const r = await api('/api/users/me');
        const u = await r.json();
        document.getElementById('email').value = u.email;
    } catch(e) {}
}

async function updateEmail() {
    const email = document.getElementById('email').value;
    try {
        const r = await api('/api/users/me', {
            method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({email})
        });
        if (r.ok) toast('Email updated');
        else { const e = await r.json(); toast(e.detail || 'Failed', false); }
    } catch(e) {}
}

async function changePassword() {
    const password = document.getElementById('new-password').value;
    if (password.length < 8) { toast('Password must be at least 8 characters', false); return; }
    try {
        const r = await api('/api/users/me', {
            method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({password})
        });
        if (r.ok) { toast('Password changed'); document.getElementById('new-password').value = ''; }
        else { const e = await r.json(); toast(e.detail || 'Failed', false); }
    } catch(e) {}
}
