# -*- coding: utf-8 -*-
"""قالب‌های HTML پنل وب استوک لند"""

LOGIN_HTML = r"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ورود · استوک لند</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700;800&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Vazirmatn',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;
  background:radial-gradient(circle at 30% 20%,#0f2419 0%,#071109 55%,#040806 100%);color:#e8f5ec;overflow:hidden}
.glow{position:fixed;width:600px;height:600px;border-radius:50%;filter:blur(120px);opacity:.35;pointer-events:none}
.g1{background:#1fc66b;top:-200px;right:-150px}
.g2{background:#0a8f4d;bottom:-220px;left:-160px}
.card{position:relative;z-index:2;width:min(92vw,400px);background:rgba(13,28,20,.72);
  border:1px solid rgba(46,204,113,.18);border-radius:24px;padding:48px 36px;
  backdrop-filter:blur(20px);box-shadow:0 30px 80px rgba(0,0,0,.5)}
.logo{width:72px;height:72px;margin:0 auto 20px;border-radius:20px;
  background:linear-gradient(135deg,#1fc66b,#0a8f4d);display:flex;align-items:center;justify-content:center;
  font-size:34px;font-weight:800;color:#04130a;box-shadow:0 12px 30px rgba(31,198,107,.35)}
h1{text-align:center;font-size:22px;font-weight:700;margin-bottom:6px}
.sub{text-align:center;font-size:13px;color:#7fb89a;margin-bottom:32px}
label{display:block;font-size:13px;color:#9fd4b5;margin:0 4px 8px}
input{width:100%;padding:14px 16px;margin-bottom:18px;border-radius:14px;
  background:rgba(7,18,12,.6);border:1px solid rgba(46,204,113,.2);color:#eafff1;font-family:inherit;font-size:15px;outline:none;transition:.2s}
input:focus{border-color:#1fc66b;box-shadow:0 0 0 3px rgba(31,198,107,.12)}
button{width:100%;padding:15px;border:0;border-radius:14px;font-family:inherit;font-size:16px;font-weight:700;
  background:linear-gradient(135deg,#1fc66b,#0a8f4d);color:#04130a;cursor:pointer;transition:.2s;margin-top:6px}
button:hover{transform:translateY(-2px);box-shadow:0 12px 28px rgba(31,198,107,.4)}
.err{background:rgba(231,76,60,.15);border:1px solid rgba(231,76,60,.3);color:#ff9b8f;
  padding:11px;border-radius:12px;font-size:13px;text-align:center;margin-bottom:18px}
</style>
</head>
<body>
<div class="glow g1"></div><div class="glow g2"></div>
<div class="card">
  <div class="logo">SL</div>
  <h1>پنل مدیریت استوک لند</h1>
  <div class="sub">برای ورود اطلاعات حساب خود را وارد کنید</div>
  {% if error %}<div class="err">نام کاربری یا رمز عبور اشتباه است</div>{% endif %}
  <form method="post" action="/login">
    <label>نام کاربری</label>
    <input name="u" autocomplete="username" required>
    <label>رمز عبور</label>
    <input name="p" type="password" autocomplete="current-password" required>
    <button type="submit">ورود به پنل</button>
  </form>
</div>
</body>
</html>"""


PANEL_HTML = r"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>پنل مدیریت · استوک لند</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700;800&display=swap');
:root{
  --bg:#060d09;--panel:#0d1c14;--panel2:#112619;--line:rgba(46,204,113,.14);
  --green:#1fc66b;--green-d:#0a8f4d;--text:#e8f5ec;--muted:#7fb89a;--muted2:#5a8870;
  --danger:#e74c3c;--warn:#f0a020;--radius:16px}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Vazirmatn',sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
::-webkit-scrollbar{width:8px;height:8px}::-webkit-scrollbar-thumb{background:rgba(46,204,113,.25);border-radius:8px}

/* ── Layout ── */
.app{display:flex;min-height:100vh}
.sidebar{width:240px;background:var(--panel);border-left:1px solid var(--line);
  padding:24px 16px;position:fixed;top:0;right:0;bottom:0;overflow-y:auto;z-index:50;transition:.3s}
.brand{display:flex;align-items:center;gap:12px;margin-bottom:32px;padding:0 8px}
.brand .ico{width:42px;height:42px;border-radius:12px;background:linear-gradient(135deg,var(--green),var(--green-d));
  display:flex;align-items:center;justify-content:center;font-weight:800;color:#04130a;font-size:18px}
.brand b{font-size:16px}.brand span{font-size:11px;color:var(--muted2);display:block}
.nav a{display:flex;align-items:center;gap:12px;padding:12px 14px;border-radius:12px;color:var(--muted);
  text-decoration:none;font-size:14px;font-weight:500;margin-bottom:4px;cursor:pointer;transition:.15s}
.nav a:hover{background:var(--panel2);color:var(--text)}
.nav a.active{background:linear-gradient(135deg,rgba(31,198,107,.18),rgba(10,143,77,.1));color:var(--green)}
.nav a .em{font-size:18px;width:24px;text-align:center}
.nav .badge{margin-inline-start:auto;background:var(--danger);color:#fff;font-size:11px;
  min-width:20px;height:20px;border-radius:10px;display:flex;align-items:center;justify-content:center;padding:0 6px}
.logout{margin-top:24px;color:var(--muted2)!important}

.main{flex:1;margin-right:240px;padding:28px 32px;min-width:0}
.topbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:28px}
.topbar h2{font-size:24px;font-weight:700}
.topbar .hint{font-size:13px;color:var(--muted2)}
.menu-btn{display:none;background:var(--panel2);border:1px solid var(--line);color:var(--text);
  width:42px;height:42px;border-radius:12px;font-size:20px;cursor:pointer}

/* ── Cards ── */
.grid{display:grid;gap:16px}
.stat-grid{grid-template-columns:repeat(auto-fill,minmax(180px,1fr))}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:22px;position:relative;overflow:hidden}
.stat::before{content:'';position:absolute;top:0;right:0;width:80px;height:80px;
  background:radial-gradient(circle,rgba(31,198,107,.12),transparent 70%)}
.stat .lbl{font-size:13px;color:var(--muted);margin-bottom:8px}
.stat .num{font-size:34px;font-weight:800;font-variant-numeric:tabular-nums}
.stat .em{position:absolute;left:18px;top:18px;font-size:22px;opacity:.5}

/* ── Panels ── */
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:22px;margin-bottom:18px}
.card h3{font-size:16px;font-weight:700;margin-bottom:16px;display:flex;align-items:center;gap:8px}
.card h3 .count{font-size:12px;color:var(--muted2);font-weight:500;margin-inline-start:auto}

/* ── Tree (catalog) ── */
.tree-root{border:1px solid var(--line);border-radius:14px;margin-bottom:12px;overflow:hidden}
.tree-head{display:flex;align-items:center;gap:10px;padding:14px 16px;background:var(--panel2);cursor:pointer;transition:.15s}
.tree-head:hover{background:rgba(31,198,107,.08)}
.tree-head .ico{font-size:20px}
.tree-head .nm{font-weight:600;font-size:15px}
.tree-head .meta{margin-inline-start:auto;font-size:12px;color:var(--muted2);display:flex;gap:8px;align-items:center}
.chip{background:rgba(31,198,107,.12);color:var(--green);padding:3px 9px;border-radius:8px;font-size:11px}
.chip.off{background:rgba(231,76,60,.12);color:#ff8a7a}
.tree-body{padding:8px 12px 12px;display:none}
.tree-body.open{display:block}
.sub-row{display:flex;align-items:center;gap:10px;padding:11px 12px;border-radius:10px;margin-top:6px;
  background:var(--bg);cursor:pointer;transition:.15s}
.sub-row:hover{background:rgba(31,198,107,.06)}
.sub-row .nm{font-size:14px}
.sub-row .meta{margin-inline-start:auto;font-size:12px;color:var(--muted2)}

/* ── Buttons ── */
.btn{display:inline-flex;align-items:center;gap:7px;padding:10px 16px;border-radius:11px;border:0;
  font-family:inherit;font-size:13.5px;font-weight:600;cursor:pointer;transition:.15s;white-space:nowrap}
.btn-pri{background:linear-gradient(135deg,var(--green),var(--green-d));color:#04130a}
.btn-pri:hover{transform:translateY(-1px);box-shadow:0 8px 20px rgba(31,198,107,.3)}
.btn-ghost{background:var(--panel2);color:var(--text);border:1px solid var(--line)}
.btn-ghost:hover{border-color:var(--green);color:var(--green)}
.btn-danger{background:rgba(231,76,60,.14);color:#ff8a7a;border:1px solid rgba(231,76,60,.25)}
.btn-danger:hover{background:rgba(231,76,60,.22)}
.btn-sm{padding:7px 12px;font-size:12.5px}
.row-actions{display:flex;gap:8px;flex-wrap:wrap}

/* ── Product cards ── */
.prod-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px}
.prod{background:var(--bg);border:1px solid var(--line);border-radius:14px;overflow:hidden;transition:.15s}
.prod:hover{border-color:rgba(31,198,107,.35);transform:translateY(-2px)}
.prod .ph{height:140px;background:var(--panel2);display:flex;align-items:center;justify-content:center;
  font-size:40px;color:var(--muted2);position:relative;overflow:hidden}
.prod .ph img{width:100%;height:100%;object-fit:cover}
.prod .tag{position:absolute;top:8px;right:8px;font-size:11px;padding:3px 9px;border-radius:8px;font-weight:600}
.prod .tag.on{background:rgba(31,198,107,.9);color:#04130a}
.prod .tag.off{background:rgba(231,76,60,.9);color:#fff}
.prod .body{padding:14px}
.prod .nm{font-weight:600;font-size:14.5px;margin-bottom:6px}
.prod .pr{color:var(--green);font-size:13px;margin-bottom:12px}
.prod .acts{display:flex;gap:6px}

/* ── Tables ── */
table{width:100%;border-collapse:collapse}
th{text-align:right;font-size:12.5px;color:var(--muted2);font-weight:600;padding:10px 12px;border-bottom:1px solid var(--line)}
td{padding:12px;font-size:13.5px;border-bottom:1px solid rgba(46,204,113,.06)}
tr:hover td{background:rgba(31,198,107,.03)}
.status{font-size:11px;padding:3px 10px;border-radius:8px;font-weight:600}
.status.new{background:rgba(240,160,32,.16);color:var(--warn)}
.status.done{background:rgba(31,198,107,.14);color:var(--green)}

/* ── Sections ── */
.sec-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}
.sec{background:var(--bg);border:1px solid var(--line);border-radius:14px;padding:18px}
.sec .hd{display:flex;align-items:center;gap:8px;font-weight:600;margin-bottom:12px}
.sec .marks{margin-inline-start:auto;display:flex;gap:5px}
.sec .mk{font-size:14px;opacity:.4}.sec .mk.on{opacity:1}
.sec textarea{width:100%;min-height:80px;background:var(--panel2);border:1px solid var(--line);
  border-radius:10px;color:var(--text);padding:10px;font-family:inherit;font-size:13px;resize:vertical;margin-bottom:10px}
.sec textarea:focus{outline:none;border-color:var(--green)}

/* ── Form / Modal ── */
.modal-bg{position:fixed;inset:0;background:rgba(0,0,0,.7);backdrop-filter:blur(4px);z-index:100;
  display:none;align-items:center;justify-content:center;padding:20px}
.modal-bg.show{display:flex}
.modal{background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:28px;
  width:min(94vw,460px);max-height:90vh;overflow-y:auto}
.modal h3{font-size:18px;margin-bottom:20px}
.field{margin-bottom:16px}
.field label{display:block;font-size:13px;color:var(--muted);margin-bottom:7px}
.field input,.field textarea,.field select{width:100%;padding:12px 14px;background:var(--bg);
  border:1px solid var(--line);border-radius:11px;color:var(--text);font-family:inherit;font-size:14px;outline:none}
.field input:focus,.field textarea:focus,.field select:focus{border-color:var(--green)}
.field textarea{min-height:70px;resize:vertical}
.modal-acts{display:flex;gap:10px;margin-top:8px}
.modal-acts .btn{flex:1;justify-content:center}
.filepick{border:2px dashed var(--line);border-radius:12px;padding:20px;text-align:center;cursor:pointer;color:var(--muted2);transition:.15s}
.filepick:hover{border-color:var(--green);color:var(--green)}
.filepick img{max-height:120px;border-radius:8px;margin-top:10px}

/* ── Toast ── */
.toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(100px);
  background:var(--panel2);border:1px solid var(--green);color:var(--text);padding:14px 24px;border-radius:12px;
  font-size:14px;z-index:200;transition:.3s;box-shadow:0 10px 30px rgba(0,0,0,.4)}
.toast.show{transform:translateX(-50%) translateY(0)}
.toast.err{border-color:var(--danger)}

/* ── Misc ── */
.empty{text-align:center;padding:50px 20px;color:var(--muted2)}
.empty .em{font-size:48px;margin-bottom:14px;opacity:.5}
.page{display:none}.page.active{display:block}
.seg{display:inline-flex;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:4px;gap:4px;margin-bottom:18px;flex-wrap:wrap}
.seg button{background:transparent;border:0;color:var(--muted);padding:9px 16px;border-radius:9px;font-family:inherit;font-size:13px;cursor:pointer;font-weight:500}
.seg button.active{background:var(--green);color:#04130a;font-weight:600}
.switch{position:relative;width:46px;height:26px;flex-shrink:0}
.switch input{display:none}
.switch .sl{position:absolute;inset:0;background:var(--panel2);border:1px solid var(--line);border-radius:26px;cursor:pointer;transition:.2s}
.switch .sl::before{content:'';position:absolute;width:18px;height:18px;right:3px;top:3px;background:var(--muted);border-radius:50%;transition:.2s}
.switch input:checked + .sl{background:var(--green)}
.switch input:checked + .sl::before{transform:translateX(-20px);background:#04130a}
.wh-day{display:flex;align-items:center;gap:12px;padding:12px;border-bottom:1px solid var(--line)}
.wh-day .dn{width:80px;font-size:14px}
.wh-day input[type=text]{flex:1;padding:8px 12px;background:var(--bg);border:1px solid var(--line);border-radius:9px;color:var(--text);font-family:inherit;font-size:13px;direction:ltr;text-align:left}

@media(max-width:880px){
  .sidebar{transform:translateX(100%)}.sidebar.open{transform:translateX(0)}
  .main{margin-right:0}.menu-btn{display:block}
}
</style>
</head>
<body>
<div class="app">
  <aside class="sidebar" id="sidebar">
    <div class="brand">
      <div class="ico">SL</div>
      <div><b>استوک لند</b><span>پنل مدیریت</span></div>
    </div>
    <nav class="nav" id="nav">
      <a data-page="dashboard" class="active"><span class="em">📊</span> داشبورد</a>
      <a data-page="catalog"><span class="em">🛍</span> محصولات</a>
      <a data-page="requests"><span class="em">📬</span> درخواست‌ها <span class="badge" id="reqBadge" style="display:none">0</span></a>
      <a data-page="users"><span class="em">👥</span> کاربران</a>
      <a data-page="sections"><span class="em">✏️</span> مدیریت بخش‌ها</a>
      <a data-page="workhours"><span class="em">🕐</span> ساعت کاری</a>
      <a data-page="settings"><span class="em">⚙️</span> تنظیمات</a>
      <a href="/logout" class="logout"><span class="em">🚪</span> خروج</a>
    </nav>
  </aside>

  <main class="main">
    <div class="topbar">
      <button class="menu-btn" onclick="document.getElementById('sidebar').classList.toggle('open')">☰</button>
      <div><h2 id="pageTitle">داشبورد</h2><div class="hint" id="pageHint">نمای کلی فروشگاه</div></div>
    </div>

    <!-- داشبورد -->
    <section class="page active" id="page-dashboard">
      <div class="grid stat-grid" id="statGrid"></div>
    </section>

    <!-- محصولات -->
    <section class="page" id="page-catalog">
      <div style="display:flex;gap:10px;margin-bottom:18px;flex-wrap:wrap">
        <button class="btn btn-pri" onclick="openCatModal(null)">➕ دسته اصلی جدید</button>
      </div>
      <div id="treeWrap"></div>
    </section>

    <!-- درخواست‌ها -->
    <section class="page" id="page-requests">
      <div class="card"><table><thead><tr>
        <th>#</th><th>محصول</th><th>نام</th><th>تماس</th><th>وضعیت</th><th></th>
      </tr></thead><tbody id="reqBody"></tbody></table></div>
    </section>

    <!-- کاربران -->
    <section class="page" id="page-users">
      <div class="seg" id="userSeg">
        <button class="active" data-f="all">همه</button>
        <button data-f="today">امروز</button>
        <button data-f="week">هفته</button>
        <button data-f="blocked">بلاک</button>
      </div>
      <div class="field" style="max-width:300px;margin-bottom:16px">
        <input id="userSearch" placeholder="🔍 جستجوی نام، آیدی یا یوزرنیم..." oninput="loadUsers()">
      </div>
      <div class="card"><table><thead><tr>
        <th>کاربر</th><th>یوزرنیم</th><th>آیدی</th><th>آخرین فعالیت</th><th></th>
      </tr></thead><tbody id="userBody"></tbody></table></div>
    </section>

    <!-- بخش‌ها -->
    <section class="page" id="page-sections">
      <div class="sec-grid" id="secGrid"></div>
    </section>

    <!-- ساعت کاری -->
    <section class="page" id="page-workhours">
      <div class="card">
        <h3>🕐 ساعت کاری هفتگی <label class="switch" style="margin-inline-start:auto"><input type="checkbox" id="whEnabled" onchange="saveWH()"><span class="sl"></span></label></h3>
        <div id="whDays"></div>
        <div style="margin-top:16px"><button class="btn btn-pri" onclick="saveWH()">💾 ذخیره ساعت کاری</button></div>
      </div>
    </section>

    <!-- تنظیمات -->
    <section class="page" id="page-settings">
      <div class="card"><h3>⚙️ تنظیمات نمایش</h3><div id="settingsList"></div></div>
    </section>
  </main>
</div>

<div class="modal-bg" id="modalBg"><div class="modal" id="modalBox"></div></div>
<div class="toast" id="toast"></div>

<script>
const $ = s => document.querySelector(s);
const api = async (url,opt={}) => {
  const r = await fetch(url,opt);
  if(r.status===401){location.href='/login';return}
  return r.json();
};
const toast = (m,err=false)=>{const t=$('#toast');t.textContent=m;t.className='toast show'+(err?' err':'');setTimeout(()=>t.className='toast',2600)};
const fa = n => String(n).replace(/\d/g,d=>'۰۱۲۳۴۵۶۷۸۹'[d]);

// ── Navigation ──
const titles={dashboard:['داشبورد','نمای کلی فروشگاه'],catalog:['محصولات','مدیریت دسته‌ها و محصولات'],
  requests:['درخواست‌ها','درخواست‌های خرید کاربران'],users:['کاربران','مدیریت کاربران ربات'],
  sections:['مدیریت بخش‌ها','محتوای منوی ربات'],workhours:['ساعت کاری','تنظیم ساعات کاری فروشگاه'],
  settings:['تنظیمات','تنظیمات نمایش ربات']};
document.querySelectorAll('#nav a[data-page]').forEach(a=>{
  a.onclick=()=>{
    document.querySelectorAll('#nav a').forEach(x=>x.classList.remove('active'));
    a.classList.add('active');
    const p=a.dataset.page;
    document.querySelectorAll('.page').forEach(x=>x.classList.remove('active'));
    $('#page-'+p).classList.add('active');
    $('#pageTitle').textContent=titles[p][0];$('#pageHint').textContent=titles[p][1];
    $('#sidebar').classList.remove('open');
    loaders[p]&&loaders[p]();
  };
});

// ── Dashboard ──
async function loadDash(){
  const d=await api('/api/dashboard');
  const cards=[['کل کاربران',d.total,'👥'],['عضو امروز',d.new_today,'🆕'],['فعال امروز',d.today,'📅'],
    ['فعال هفته',d.week,'📆'],['محصولات',d.products,'🛍'],['دسته‌ها',d.categories,'📁'],
    ['درخواست جدید',d.reqs_new,'📬'],['بلاک‌شده',d.blocked,'🚫']];
  $('#statGrid').innerHTML=cards.map(c=>`<div class="stat"><span class="em">${c[2]}</span><div class="lbl">${c[0]}</div><div class="num">${fa(c[1])}</div></div>`).join('');
  if(d.reqs_new>0){$('#reqBadge').style.display='flex';$('#reqBadge').textContent=fa(d.reqs_new)}
  else $('#reqBadge').style.display='none';
}

// ── Catalog tree ──
async function loadTree(){
  const tree=await api('/api/tree');
  const w=$('#treeWrap');
  if(!tree.length){w.innerHTML=`<div class="empty"><div class="em">📦</div>هنوز دسته‌ای ثبت نشده. اولین دسته را بسازید.</div>`;return}
  w.innerHTML=tree.map(r=>`
    <div class="tree-root">
      <div class="tree-head" onclick="this.nextElementSibling.classList.toggle('open')">
        <span class="ico">${r.icon}</span><span class="nm">${r.name}</span>
        <span class="meta">
          <span class="chip ${r.active?'':'off'}">${r.active?'فعال':'غیرفعال'}</span>
          <span>${fa(r.subs.length)} زیردسته</span>
        </span>
      </div>
      <div class="tree-body">
        <div class="row-actions" style="margin:8px 4px 12px">
          <button class="btn btn-ghost btn-sm" onclick="event.stopPropagation();openSubModal(${r.id},null)">➕ زیردسته</button>
          <button class="btn btn-ghost btn-sm" onclick="event.stopPropagation();openCatModal(${r.id},'${r.icon}','${r.name.replace(/'/g,"\\'")}')">✏️ ویرایش</button>
          <button class="btn btn-danger btn-sm" onclick="event.stopPropagation();delCat(${r.id},'${r.name.replace(/'/g,"\\'")}',true)">🗑 حذف دسته</button>
        </div>
        ${r.subs.map(s=>`
          <div class="sub-row" onclick="openProducts(${s.id},'${s.icon} ${s.name.replace(/'/g,"\\'")}',${r.id})">
            <span>${s.icon}</span><span class="nm">${s.name}</span>
            <span class="meta">${fa(s.product_count)} محصول ›</span>
          </div>`).join('')||'<div style="color:var(--muted2);font-size:13px;padding:8px 4px">زیردسته‌ای نیست</div>'}
      </div>
    </div>`).join('');
}

// ── Products of a sub ──
async function openProducts(subId,title,rootId){
  const prods=await api('/api/products/'+subId);
  showModal(`
    <h3>📦 ${title}</h3>
    <button class="btn btn-pri" style="width:100%;justify-content:center;margin-bottom:16px" onclick="openProdModal(${subId},null)">➕ افزودن محصول</button>
    <div class="prod-grid">
      ${prods.length?prods.map(p=>`
        <div class="prod">
          <div class="ph">${p.photo_url?`<img src="${p.photo_url}">`:'📱'}<span class="tag ${p.active?'on':'off'}">${p.active?'فعال':'غیرفعال'}</span></div>
          <div class="body">
            <div class="nm">${p.name}</div><div class="pr">💰 ${p.price}</div>
            <div class="acts">
              <button class="btn btn-ghost btn-sm" style="flex:1;justify-content:center" onclick='openProdModal(${subId},${JSON.stringify(p)})'>✏️</button>
              <button class="btn btn-danger btn-sm" onclick="delProd(${p.id},'${p.name.replace(/'/g,"\\'")}',${subId},'${title.replace(/'/g,"\\'")}',${rootId})">🗑</button>
            </div>
          </div>
        </div>`).join(''):'<div class="empty" style="grid-column:1/-1"><div class="em">📱</div>محصولی در این زیردسته نیست</div>'}
    </div>
    <div class="row-actions" style="margin-top:16px;border-top:1px solid var(--line);padding-top:16px">
      <button class="btn btn-ghost btn-sm" onclick="openSubModal(${rootId},{id:${subId},name:'${title.replace(/'/g,"\\'")}'})">✏️ نام زیردسته</button>
      <button class="btn btn-danger btn-sm" onclick="delCat(${subId},'${title.replace(/'/g,"\\'")}',false)">🗑 حذف زیردسته</button>
    </div>`);
}

// ── Category modal ──
function openCatModal(id,icon='',name=''){
  const edit=id&&icon!=='';
  showModal(`<h3>${edit?'✏️ ویرایش دسته':'➕ دسته اصلی جدید'}</h3>
    <div class="field"><label>آیکون (ایموجی)</label><input id="cIcon" value="${icon||'📱'}" maxlength="4"></div>
    <div class="field"><label>نام دسته</label><input id="cName" value="${name}" placeholder="مثلاً موبایل"></div>
    <div class="modal-acts">
      <button class="btn btn-ghost" onclick="closeModal()">انصراف</button>
      <button class="btn btn-pri" onclick="saveCat(${edit?id:'null'})">${edit?'ذخیره':'افزودن'}</button>
    </div>`);
}
async function saveCat(id){
  const icon=$('#cIcon').value.trim(),name=$('#cName').value.trim();
  if(!name)return toast('نام دسته را وارد کنید',true);
  if(id){await api('/api/category/'+id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({icon,name})});toast('دسته ویرایش شد')}
  else{await api('/api/category',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({icon,name})});toast('دسته اضافه شد')}
  closeModal();loadTree();
}

// ── Sub modal ──
function openSubModal(rootId,sub){
  const edit=sub&&sub.id;
  showModal(`<h3>${edit?'✏️ ویرایش زیردسته':'➕ زیردسته جدید'}</h3>
    <div class="field"><label>آیکون</label><input id="sIcon" value="${edit&&sub.icon?sub.icon:'📲'}" maxlength="4"></div>
    <div class="field"><label>نام زیردسته</label><input id="sName" value="${edit?(sub.name||'').replace(/^.*?\s/,''):''}" placeholder="مثلاً سامسونگ"></div>
    <div class="modal-acts">
      <button class="btn btn-ghost" onclick="closeModal()">انصراف</button>
      <button class="btn btn-pri" onclick="saveSub(${rootId},${edit?sub.id:'null'})">${edit?'ذخیره':'افزودن'}</button>
    </div>`);
}
async function saveSub(rootId,id){
  const icon=$('#sIcon').value.trim(),name=$('#sName').value.trim();
  if(!name)return toast('نام زیردسته را وارد کنید',true);
  if(id){await api('/api/category/'+id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({icon,name})});toast('زیردسته ویرایش شد')}
  else{await api('/api/category',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({icon,name,parent_id:rootId})});toast('زیردسته اضافه شد')}
  closeModal();loadTree();
}

async function delCat(id,name,isRoot){
  if(!confirm(`«${name}» و تمام محتوای داخلش برای همیشه حذف شود؟`))return;
  await api('/api/category/'+id,{method:'DELETE'});
  toast('حذف شd'.replace('d','شد'));closeModal();loadTree();
}

// ── Product modal ──
let _photoFile=null;
function openProdModal(subId,p){
  _photoFile=null;
  const edit=p&&p.id;
  showModal(`<h3>${edit?'✏️ ویرایش محصول':'➕ محصول جدید'}</h3>
    <div class="field"><label>نام محصول</label><input id="pName" value="${edit?p.name:''}"></div>
    <div class="field"><label>قیمت</label><input id="pPrice" value="${edit?p.price:''}" placeholder="مثلاً ۱۲٬۵۰۰٬۰۰۰ تومان"></div>
    <div class="field"><label>توضیحات</label><textarea id="pDesc">${edit&&p.description?p.description:''}</textarea></div>
    <div class="field"><label>لینک سایت (اختیاری)</label><input id="pUrl" value="${edit&&p.site_url?p.site_url:''}" dir="ltr" placeholder="https://stland.ir/..."></div>
    <div class="field"><label>عکس محصول</label>
      <div class="filepick" onclick="$('#pPhoto').click()" id="pickBox">
        ${edit&&p.photo_url?`<img src="${p.photo_url}" id="prevImg">`:'📷 برای انتخاب عکس کلیک کنید'}
      </div>
      <input type="file" id="pPhoto" accept="image/*" style="display:none" onchange="onPhoto(this)">
    </div>
    <div class="modal-acts">
      <button class="btn btn-ghost" onclick="closeModal()">انصراف</button>
      <button class="btn btn-pri" onclick="saveProd(${subId},${edit?p.id:'null'})">${edit?'ذخیره':'افزودن'}</button>
    </div>`);
}
function onPhoto(inp){
  if(!inp.files[0])return;_photoFile=inp.files[0];
  const r=new FileReader();r.onload=e=>{$('#pickBox').innerHTML=`<img src="${e.target.result}">`};r.readAsDataURL(inp.files[0]);
}
async function saveProd(subId,id){
  const fd=new FormData();
  fd.append('name',$('#pName').value.trim());
  fd.append('price',$('#pPrice').value.trim());
  fd.append('description',$('#pDesc').value.trim());
  fd.append('site_url',$('#pUrl').value.trim());
  if(!id)fd.append('category_id',subId);
  if(_photoFile)fd.append('photo',_photoFile);
  if(!$('#pName').value.trim()||!$('#pPrice').value.trim())return toast('نام و قیمت لازم است',true);
  const url=id?'/api/product/'+id:'/api/product';
  const method=id?'PUT':'POST';
  const r=await fetch(url,{method,body:fd});
  if(r.ok){toast(id?'محصول ویرایش شد':'محصول اضافه شد');closeModal();loadTree()}
  else toast('خطا در ذخیره',true);
}
async function delProd(id,name,subId,title,rootId){
  if(!confirm(`محصول «${name}» حذف شود؟`))return;
  await api('/api/product/'+id,{method:'DELETE'});
  toast('محصول حذف شد');openProducts(subId,title,rootId);loadTree();
}

// ── Requests ──
async function loadReqs(){
  const rows=await api('/api/requests');
  $('#reqBody').innerHTML=rows.length?rows.map(r=>`
    <tr>
      <td>${fa(r.id)}</td><td>${r.product_name}</td>
      <td>${r.first_name||'—'}</td><td dir="ltr">${r.phone}</td>
      <td><span class="status ${r.status}">${r.status==='new'?'جدید':'پیگیری شد'}</span></td>
      <td>${r.status==='new'?`<button class="btn btn-ghost btn-sm" onclick="doneReq(${r.id})">✓ پیگیری شد</button>`:''}</td>
    </tr>`).join(''):'<tr><td colspan="6"><div class="empty"><div class="em">📭</div>درخواستی ثبت نشده</div></td></tr>';
}
async function doneReq(id){await api('/api/request/'+id+'/done',{method:'PUT'});toast('علامت‌گذاری شد');loadReqs();loadDash();}

// ── Users ──
let userFilter='all';
document.querySelectorAll('#userSeg button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('#userSeg button').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');userFilter=b.dataset.f;loadUsers();
});
async function loadUsers(){
  const q=$('#userSearch').value.trim();
  const rows=await api(`/api/users?filter=${userFilter}&q=${encodeURIComponent(q)}`);
  $('#userBody').innerHTML=rows.length?rows.map(u=>`
    <tr>
      <td>${u.is_blocked?'🚫 ':''}${u.first_name||'—'}</td>
      <td>${u.username?'@'+u.username:'—'}</td>
      <td dir="ltr">${u.user_id}</td>
      <td style="font-size:12px;color:var(--muted2)">${(u.last_seen||'').slice(0,16)}</td>
      <td><button class="btn ${u.is_blocked?'btn-ghost':'btn-danger'} btn-sm" onclick="toggleBlock(${u.user_id})">${u.is_blocked?'رفع بلاک':'بلاک'}</button></td>
    </tr>`).join(''):'<tr><td colspan="5"><div class="empty"><div class="em">👤</div>کاربری یافت نشد</div></td></tr>';
}
async function toggleBlock(uid){await api('/api/user/'+uid+'/block',{method:'PUT'});toast('انجام شد');loadUsers();}

// ── Sections ──
async function loadSections(){
  const secs=await api('/api/sections');
  $('#secGrid').innerHTML=secs.map(s=>`
    <div class="sec">
      <div class="hd">${s.name}
        <span class="marks">
          <span class="mk ${s.text?'on':''}" title="متن">📝</span>
          <span class="mk ${s.has_banner?'on':''}" title="بنر">🖼</span>
          <span class="mk ${s.buttons_enabled&&s.buttons.length?'on':''}" title="دکمه">🔗</span>
        </span>
      </div>
      <textarea id="sec_${s.key}" placeholder="متن این بخش...">${s.text||''}</textarea>
      <div class="row-actions">
        <button class="btn btn-pri btn-sm" onclick="saveSecText('${s.key}')">💾 ذخیره متن</button>
        <button class="btn btn-ghost btn-sm" onclick="openBtnModal('${s.key}','${s.name}')">🔗 دکمه‌ها (${fa(s.buttons.length)})</button>
      </div>
    </div>`).join('');
}
async function saveSecText(key){
  await api('/api/section/'+key+'/text',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:$('#sec_'+key).value})});
  toast('متن ذخیره شد');
}
async function openBtnModal(key,name){
  const secs=await api('/api/sections');
  const s=secs.find(x=>x.key===key);
  showModal(`<h3>🔗 دکمه‌های ${name}</h3>
    <div style="margin-bottom:16px">
      ${s.buttons.map(b=>`<div style="display:flex;gap:8px;align-items:center;padding:10px;background:var(--bg);border-radius:10px;margin-bottom:8px">
        <span style="flex:1;font-size:13px">🔗 ${b.title}</span>
        <button class="btn btn-danger btn-sm" onclick="delBtn('${key}','${b.id}','${name}')">حذف</button>
      </div>`).join('')||'<div style="color:var(--muted2);font-size:13px;text-align:center;padding:14px">دکمه‌ای نیست</div>'}
    </div>
    <div class="field"><label>عنوان دکمه</label><input id="btnTitle" placeholder="مثلاً اینستاگرام"></div>
    <div class="field"><label>لینک</label><input id="btnUrl" dir="ltr" placeholder="https://..."></div>
    <div class="modal-acts">
      <button class="btn btn-ghost" onclick="closeModal()">بستن</button>
      <button class="btn btn-pri" onclick="addBtn('${key}','${name}')">➕ افزودن دکمه</button>
    </div>`);
}
async function addBtn(key,name){
  const title=$('#btnTitle').value.trim(),url=$('#btnUrl').value.trim();
  if(!title||!url)return toast('عنوان و لینک لازم است',true);
  await api('/api/section/'+key+'/button',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,url})});
  toast('دکمه اضافه شد');openBtnModal(key,name);loadSections();
}
async function delBtn(key,bid,name){
  await api('/api/section/'+key+'/button/'+bid,{method:'DELETE'});
  toast('دکمه حذف شد');openBtnModal(key,name);loadSections();
}

// ── Workhours ──
let _wh={};
async function loadWH(){
  _wh=await api('/api/workhours');
  $('#whEnabled').checked=_wh.enabled!==false;
  const days=['0','1','2','3','4','5','6'];
  const names={'0':'شنبه','1':'یکشنبه','2':'دوشنبه','3':'سه‌شنبه','4':'چهارشنبه','5':'پنجشنبه','6':'جمعه'};
  $('#whDays').innerHTML=days.map(d=>{
    const day=(_wh.schedule||{})[d]||{open:false,shifts:[]};
    const shifts=day.shifts.map(s=>`${s.from}-${s.to}`).join(',');
    return `<div class="wh-day">
      <span class="dn">${names[d]}</span>
      <label class="switch"><input type="checkbox" data-day="${d}" class="whOpen" ${day.open?'checked':''}><span class="sl"></span></label>
      <input type="text" class="whShift" data-day="${d}" value="${shifts}" placeholder="11:00-14:00,17:00-23:00">
    </div>`;
  }).join('');
}
async function saveWH(){
  const sched={};
  document.querySelectorAll('.whOpen').forEach(cb=>{
    const d=cb.dataset.day;
    const shiftStr=document.querySelector(`.whShift[data-day="${d}"]`).value.trim();
    const shifts=shiftStr?shiftStr.split(',').map(p=>{const[f,t]=p.split('-');return{from:(f||'').trim(),to:(t||'').trim()}}).filter(s=>s.from&&s.to):[];
    sched[d]={open:cb.checked,shifts};
  });
  _wh.enabled=$('#whEnabled').checked;_wh.schedule=sched;
  if(!_wh.msg_open)_wh.msg_open='✅ هم‌اکنون باز است';
  if(!_wh.msg_closed)_wh.msg_closed='🔴 هم‌اکنون بسته است';
  await api('/api/workhours',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(_wh)});
  toast('ساعت کاری ذخیره شد');
}

// ── Settings ──
const SETTING_LABELS={show_workhours_menu:'نمایش ساعت کاری در منو',show_catalog_menu:'نمایش محصولات در منو',
  notify_new_user:'اعلان عضو جدید',store_open:'فروشگاه باز است'};
async function loadSettings(){
  const s=await api('/api/settings');
  $('#settingsList').innerHTML=Object.entries(SETTING_LABELS).map(([k,lbl])=>`
    <div style="display:flex;align-items:center;padding:14px 4px;border-bottom:1px solid var(--line)">
      <span style="font-size:14px">${lbl}</span>
      <label class="switch" style="margin-inline-start:auto"><input type="checkbox" ${s[k]!==false?'checked':''} onchange="setSetting('${k}',this.checked)"><span class="sl"></span></label>
    </div>`).join('');
}
async function setSetting(k,v){
  await api('/api/settings',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({[k]:v})});
  toast('تنظیمات ذخیره شد');
}

// ── Modal helpers ──
function showModal(html){$('#modalBox').innerHTML=html;$('#modalBg').classList.add('show')}
function closeModal(){$('#modalBg').classList.remove('show')}
$('#modalBg').onclick=e=>{if(e.target.id==='modalBg')closeModal()};

const loaders={dashboard:loadDash,catalog:loadTree,requests:loadReqs,users:loadUsers,
  sections:loadSections,workhours:loadWH,settings:loadSettings};
loadDash();
setInterval(loadDash,30000);
</script>
</body>
</html>"""
