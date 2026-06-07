// Token Relay - Admin Portal
// --- Utilities ---
function toast(msg, ok=true) {
    const container = document.getElementById('toast-container');
    if(!container) return;
    const t = document.createElement('div');
    t.className = 'toast ' + (ok?'toast-success':'toast-error');
    t.textContent = msg;
    container.appendChild(t);
    setTimeout(() => { t.style.opacity='0'; t.style.transition='opacity .3s'; setTimeout(()=>t.remove(),300); }, 3500);
}

function formatCredits(c) { return ((c||0)/100).toFixed(2); }
function formatNum(n) { return (n||0).toLocaleString(); }
function fmtDate(d) { return d ? new Date(d).toLocaleString('zh-CN') : '-'; }
function fmtDateShort(d) { return d ? new Date(d).toLocaleDateString('zh-CN') : '-'; }

async function api(path, opts={}) {
    const headers = opts.headers || {};
    if(opts.body && typeof opts.body==='object') {
        headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(opts.body);
    }
    const res = await fetch(path, { credentials:'include', ...opts, headers });
    if(res.status===401) { window.location.href='/admin/login'; throw new Error('Unauthorized'); }
    if(res.status===204) return null;
    const data = await res.json();
    if(!res.ok) throw new Error(data.detail||'Request failed');
    return data;
}

function logout() {
    document.cookie = 'token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
    window.location.href = '/admin/login';
}

// --- Nav Highlight ---
(function(){
    const path = window.location.pathname;
    const map = {
        '/admin':'dashboard','/admin/users':'users','/admin/models':'models',
        '/admin/keys':'keys','/admin/logs':'logs','/admin/settings':'settings',
    };
    const id = map[path];
    if(id) { const el = document.getElementById('nav-'+id); if(el) el.classList.add('active'); }
})();

// --- Modal ---
function openModal(id) { document.getElementById(id).classList.add('open'); }
function closeModal(id) { document.getElementById(id).classList.remove('open'); }
window.addEventListener('click', function(e) {
    if(e.target.classList.contains('modal-overlay')) e.target.classList.remove('open');
});

// --- Pagination ---
function renderPager(containerId, page, pages, fnName) {
    const el = document.getElementById(containerId);
    if(!el||pages<=1) { if(el)el.innerHTML=''; return; }
    let h = '';
    for(let i=1;i<=pages&&i<=20;i++) {
        h += `<button onclick="${fnName}(${i})" class="${i===page?'active':''}">${i}</button>`;
    }
    el.innerHTML = h;
}
