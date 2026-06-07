// Token Relay - User Portal
let page = 1;

// --- Utilities ---
function toast(msg, ok=true) {
    const container = document.getElementById('toast-container');
    if(!container) return;
    const t = document.createElement('div');
    t.className = 'toast ' + (ok?'toast-success':'toast-error');
    t.textContent = msg;
    container.appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity .3s'; setTimeout(() => t.remove(), 300); }, 3500);
}

function formatCredits(c) { return ((c||0)/100).toFixed(2); }
function formatNum(n) { return (n||0).toLocaleString(); }
function fmtDate(d) { return d ? new Date(d).toLocaleString('zh-CN') : '-'; }
function fmtDateShort(d) { return d ? new Date(d).toLocaleDateString('zh-CN') : '-'; }

async function api(path, opts={}) {
    const headers = opts.headers || {};
    if(opts.body && typeof opts.body === 'object' && !(opts.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(opts.body);
    }
    const res = await fetch(path, { credentials:'include', ...opts, headers });
    if(res.status===401) { window.location.href='/login'; throw new Error('Unauthorized'); }
    if(res.status===204) return null;
    const data = await res.json();
    if(!res.ok) throw new Error(data.detail||'Request failed');
    return data;
}

function logout() {
    document.cookie = 'token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
    window.location.href = '/login';
}

// --- Nav Highlight ---
(function(){
    const path = window.location.pathname;
    document.querySelectorAll('.topnav-links a').forEach(a => {
        if(a.getAttribute('href')===path) a.classList.add('active');
    });
})();

// --- Load Nav Info ---
(async function(){
    try {
        const u = await api('/api/users/me');
        const email = document.getElementById('nav-email');
        const bal = document.getElementById('nav-balance');
        if(email) email.textContent = u.email;
        if(bal) bal.textContent = '$'+formatCredits(u.credit_balance);
    } catch(e) {}
})();

function renderPager(data) {
    const el = document.getElementById('pager');
    if(!el) return;
    if(data.pages<=1) { el.innerHTML=''; return; }
    const fn = window.location.pathname.includes('usage')?'loadUsage':'loadBilling';
    let h = '';
    for(let i=1;i<=data.pages&&i<=10;i++) {
        h += `<button onclick="${fn}(${i})" class="${i===data.page?'active':''}">${i}</button>`;
    }
    el.innerHTML = h;
}

// ====== DASHBOARD ======
async function loadDashboard() {
    try {
        const [user,keys,stats,logs] = await Promise.all([
            api('/api/users/me'), api('/api/users/me/keys'),
            api('/api/logs/stats'), api('/api/logs/usage?page=1&size=5')
        ]);
        const set = (id,v) => { const e=document.getElementById(id); if(e)e.textContent=v; };
        set('balance','$'+formatCredits(user.credit_balance));
        set('keys-count', keys.length);
        set('requests-today', formatNum(stats.total_requests));
        set('tokens-today', formatNum(stats.total_tokens));

        const tbody = document.getElementById('recent-logs');
        if(tbody) {
            if(logs.items.length===0) {
                tbody.innerHTML = '<tr><td colspan="5"><div class="empty-state"><p>No requests yet. Make your first API call!</p></div></td></tr>';
            } else {
                tbody.innerHTML = logs.items.map(l => `
                    <tr>
                        <td class="text-sm">${fmtDate(l.created_at)}</td>
                        <td>${l.model}</td>
                        <td>${formatNum(l.total_tokens)}</td>
                        <td class="text-mono">$${formatCredits(l.credits_consumed)}</td>
                        <td><span class="badge ${l.status==='success'?'badge-success':'badge-danger'}">${l.status}</span></td>
                    </tr>`).join('');
            }
        }
    } catch(e) { console.error(e); }
}

// ====== MODELS ======
async function loadModels() {
    try {
        const models = await api('/v1/public-models');
        const grid = document.getElementById('model-grid');
        if(!grid) return;
        if(!models||models.length===0) {
            grid.innerHTML = '<div class="empty-state" style="grid-column:1/-1;"><p>No models available</p></div>';
            return;
        }
        grid.innerHTML = models.map(m => {
            const inp = m.input_price?'$'+(m.input_price/100).toFixed(4):'auto';
            const out = m.output_price?'$'+(m.output_price/100).toFixed(4):'auto';
            return `<div class="model-card">
                <div class="provider-tag">${m.provider?m.provider.toUpperCase():''}</div>
                <div class="model-name">${m.display_name||m.id}</div>
                <div class="model-id">${m.id}</div>
                <div class="pricing-row">
                    <div class="price"><strong>${inp}</strong><span>Input / 1K tok</span></div>
                    <div class="price"><strong>${out}</strong><span>Output / 1K tok</span></div>
                </div>
                <div class="feature-tags">
                    ${m.supports_streaming?'<span class="badge badge-success">Streaming</span>':''}
                    ${m.supports_vision?'<span class="badge badge-info">Vision</span>':''}
                </div>
            </div>`;
        }).join('');
    } catch(e) { const g=document.getElementById('model-grid'); if(g)g.innerHTML='<div class="empty-state" style="grid-column:1/-1;"><p>Failed to load models</p></div>'; }
}

// ====== KEYS ======
async function loadKeys() {
    try {
        const keys = await api('/api/users/me/keys');
        const list = document.getElementById('keys-list');
        if(!list) return;
        if(keys.length===0) { list.innerHTML='<div class="empty-state"><p>No API keys yet. Create one above.</p></div>'; return; }
        list.innerHTML = keys.map(k => `
            <div class="key-item">
                <div class="key-info">
                    <div class="key-name">${k.name}</div>
                    <div class="key-meta"><span class="key-prefix">${k.key_prefix}...</span> &middot; Created ${fmtDateShort(k.created_at)} &middot; ${k.last_used_at?'Last used '+fmtDateShort(k.last_used_at):'Never used'}</div>
                </div>
                <button class="btn btn-sm btn-danger" onclick="deleteKey('${k.id}')">Delete</button>
            </div>`).join('');
    } catch(e) {}
}

async function createKey() {
    const inp = document.getElementById('key-name');
    const name = inp?(inp.value||'default'):'default';
    try {
        const data = await api('/api/users/me/keys', {method:'POST', body:{name}});
        const el = document.getElementById('new-key');
        if(el) el.style.display='block';
        const code = document.getElementById('full-key-display');
        if(code) code.textContent = data.full_key;
        if(inp) inp.value = '';
        loadKeys();
        toast('API key created');
    } catch(e) { toast(e.message,false); }
}

function copyKey() {
    const code = document.getElementById('full-key-display');
    if(!code) return;
    navigator.clipboard.writeText(code.textContent).then(()=>toast('Copied to clipboard'));
}

async function deleteKey(id) {
    if(!confirm('Delete this key? It will stop working immediately.')) return;
    try { await api('/api/users/me/keys/'+id, {method:'DELETE'}); toast('Key deleted'); loadKeys(); }
    catch(e) { toast(e.message,false); }
}

// ====== USAGE ======
async function loadUsage(p=1) {
    page = p;
    try {
        const params = new URLSearchParams({page:p, size:15});
        const model = document.getElementById('filter-model');
        const from = document.getElementById('filter-from');
        const to = document.getElementById('filter-to');
        if(model&&model.value) params.set('model',model.value);
        if(from&&from.value) params.set('from_date',from.value);
        if(to&&to.value) params.set('to_date',to.value);

        const [stats,data] = await Promise.all([
            api('/api/logs/stats?'+params.toString().replace(/page=\d+&size=\d+/,'')),
            api('/api/logs/usage?'+params)
        ]);
        const set = (id,v) => { const e=document.getElementById(id); if(e)e.textContent=v; };
        set('s-requests', formatNum(stats.total_requests));
        set('s-tokens', formatNum(stats.total_tokens));
        set('s-credits', '$'+formatCredits(stats.total_credits));

        const tbody = document.getElementById('log-table');
        if(tbody) {
            if(data.items.length===0) { tbody.innerHTML='<tr><td colspan="8"><div class="empty-state"><p>No usage data</p></div></td></tr>'; }
            else {
                tbody.innerHTML = data.items.map(l => `
                    <tr>
                        <td class="text-sm">${fmtDate(l.created_at)}</td>
                        <td>${l.model}</td>
                        <td>${l.provider}</td>
                        <td>${formatNum(l.prompt_tokens)}</td>
                        <td>${formatNum(l.completion_tokens)}</td>
                        <td class="text-mono">$${formatCredits(l.credits_consumed)}</td>
                        <td>${l.latency_ms?l.latency_ms+'ms':'-'}</td>
                        <td><span class="badge ${l.status==='success'?'badge-success':'badge-danger'}">${l.status}</span></td>
                    </tr>`).join('');
            }
        }
        renderPager(data);
    } catch(e) {}
}

// ====== BILLING ======
async function loadBilling(p=1) {
    try {
        const params = new URLSearchParams({page:p, size:15});
        const type = document.getElementById('txn-type');
        if(type&&type.value) params.set('type',type.value);

        const [bal,data] = await Promise.all([
            api('/api/billing/balance'),
            api('/api/billing/transactions?'+params)
        ]);
        const bel = document.getElementById('balance');
        if(bel) bel.textContent = '$'+formatCredits(bal.credit_balance);

        const tbody = document.getElementById('txn-table');
        if(tbody) {
            if(data.items.length===0) { tbody.innerHTML='<tr><td colspan="5"><div class="empty-state"><p>No transactions</p></div></td></tr>'; }
            else {
                const names = {purchase:'Purchase',consumption:'Consumption',refund:'Refund',admin_adjust:'Adjustment'};
                const badges = {purchase:'badge-success',consumption:'badge-danger',refund:'badge-neutral',admin_adjust:'badge-warning'};
                tbody.innerHTML = data.items.map(t => {
                    const sign = t.amount>0?'+':'';
                    return `<tr>
                        <td class="text-sm">${fmtDate(t.created_at)}</td>
                        <td><span class="badge ${badges[t.type]||'badge-neutral'}">${names[t.type]||t.type}</span></td>
                        <td class="text-mono">${sign}$${formatCredits(Math.abs(t.amount))}</td>
                        <td class="text-mono">$${formatCredits(t.balance_after)}</td>
                        <td>${t.note||'-'}</td>
                    </tr>`;
                }).join('');
            }
        }
        renderPager(data);
    } catch(e) {}
}

// ====== SETTINGS ======
async function loadSettings() {
    try {
        const u = await api('/api/users/me');
        const email = document.getElementById('email');
        if(email) email.value = u.email;
        const info = document.getElementById('profile-info');
        if(info) {
            info.innerHTML = `
                <p style="margin-bottom:6px;"><strong>Email:</strong> ${u.email}</p>
                <p style="margin-bottom:6px;"><strong>Role:</strong> ${u.role==='admin'?'Administrator':'User'}</p>
                <p style="margin-bottom:6px;"><strong>Balance:</strong> <span class="text-mono">$${formatCredits(u.credit_balance)}</span></p>
                <p><strong>Joined:</strong> ${fmtDate(u.created_at)}</p>`;
        }
    } catch(e) {}
}

async function updateEmail() {
    const inp = document.getElementById('email');
    if(!inp) return;
    const email = inp.value;
    if(!email.includes('@')) { toast('Please enter a valid email',false); return; }
    try { await api('/api/users/me', {method:'PATCH', body:{email}}); toast('Email updated'); }
    catch(e) { toast(e.message,false); }
}

async function changePassword() {
    const inp = document.getElementById('new-password');
    if(!inp) return;
    const password = inp.value;
    if(password.length<8) { toast('Password must be at least 8 characters',false); return; }
    try { await api('/api/users/me', {method:'PATCH', body:{password}}); toast('Password changed'); inp.value=''; }
    catch(e) { toast(e.message,false); }
}
