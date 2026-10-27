// 宏觀監控儀表板：共用頂部目錄欄。新增子頁面時在 PAGES 加一列即可（放進群組的 items 就會出現在下拉選單）。
// 改了本檔要同步把各頁 <script src="nav.js?v=…"> 的版本號改新（GitHub Pages 快取 10 分鐘，舊 nav.js 會配到新頁面）
// 另含共用「點燈號跳轉」：燈號元素寫 class="signal" data-to="目標 id" role="link" tabindex="0"，
// 點擊（或 Enter／空白鍵）平滑捲到目標所在的 .card（無 .card 則目標本身），並閃一下紅框。
// 跨頁跳轉：連結寫 頁面.html#目標id（如 rates.html#chart-oil），進頁後同樣捲到該卡片並閃框。
(() => {
  const PAGES = [
    { href: "risk-chain.html", label: "風險傳導鏈" },
    { label: "宏觀數據", items: [
      { href: "rates.html", label: "貨幣成本", desc: "通膨、Fed 利率路徑、公債與信用利率" },
      { href: "index.html", label: "就業狀況", desc: "初領失業金、非農、失業率 vs u*" },
      { href: "margin.html", label: "融資槓桿", desc: "FINRA 融資年增、槓桿熱度、Fed 救援空間" },
    ] },
    { label: "產業數據", items: [
      { href: "datacenter.html", label: "資料中心成本", desc: "每 $100 AI 資本支出沿供應鏈的流向" },
      { href: "asml.html", label: "ASML產能分配", desc: "邏輯 vs 記憶體系統銷售金額與占比" },
      { href: "capex.html", label: "AI半導體產業看板", desc: "雲端大廠 CapEx 季度趨勢與 YoY" },
      { href: "csp-cashflow.html", label: "CSP 現金流", desc: "雲端大廠 OCF vs CapEx、FCF 與燈號" },
    ] },
  ];
  const here = location.pathname.split("/").pop() || "index.html";
  const css = `
.site-nav { position: sticky; top: 0; z-index: 50; background: #22262B; color: #F2F1EE;
  font-family: "Noto Sans TC", "Microsoft JhengHei", "PingFang TC", system-ui, sans-serif; }
.site-nav .in { max-width: 1180px; margin: 0 auto; padding: 0 16px; display: flex; align-items: center;
  gap: 8px 24px; flex-wrap: wrap; min-height: 52px; }
.site-nav .brand { font-size: 17px; font-weight: 700; letter-spacing: 1px; color: #fff; text-decoration: none; }
.site-nav .tabs { display: flex; gap: 4px; flex-wrap: wrap; }
.site-nav .tabs a { color: #B9BEC4; text-decoration: none; font-size: 14px; padding: 15px 12px 13px;
  border-bottom: 3px solid transparent; }
.site-nav .tabs a:hover { color: #fff; }
.site-nav .tabs a[aria-current="page"] { color: #fff; font-weight: 700; border-bottom-color: #E8B04A; }
.site-nav a:focus-visible, .site-nav .grp > button:focus-visible { outline: 2px solid #E8B04A; outline-offset: -2px; }
.site-nav .grp { position: relative; }
.site-nav .grp > button { font: inherit; font-size: 14px; color: #B9BEC4; background: none; border: 0; border-radius: 0; cursor: pointer;
  padding: 15px 12px 13px; border-bottom: 3px solid transparent; }
.site-nav .grp > button::after { content: ""; display: inline-block; margin-left: 6px; vertical-align: 2px;
  border: 4px solid transparent; border-top-color: currentColor; border-bottom: 0; }
.site-nav .grp:hover > button, .site-nav .grp.open > button { color: #fff; }
.site-nav .grp.current > button { color: #fff; font-weight: 700; border-bottom-color: #E8B04A; }
.site-nav .menu { display: none; position: absolute; top: 100%; left: 0; min-width: 280px; max-width: calc(100vw - 32px);
  background: #2C3137; border-radius: 0 0 10px 10px; box-shadow: 0 10px 24px rgba(0,0,0,.28); padding: 6px; }
.site-nav .grp:last-child .menu { left: auto; right: 0; }
.site-nav .grp:hover .menu, .site-nav .grp:focus-within .menu, .site-nav .grp.open .menu { display: block; }
.site-nav .menu a { display: block; padding: 9px 12px; border: 0; border-radius: 6px; border-left: 3px solid transparent; }
.site-nav .menu a b { display: block; color: #fff; font-size: 14px; font-weight: 600; }
.site-nav .menu a span { display: block; color: #9AA0A6; font-size: 12px; margin-top: 1px; }
.site-nav .menu a:hover { background: rgba(255,255,255,.07); }
.site-nav .menu a[aria-current="page"] { border-left-color: #E8B04A; background: rgba(232,176,74,.10); }
.signal[data-to] { cursor: pointer; transition: border-color .15s, box-shadow .15s; }
.signal[data-to]:hover, .signal[data-to]:focus-visible { border-color: var(--lamp); box-shadow: 0 2px 10px rgba(0,0,0,.08); outline: none; }
.jump { scroll-margin-top: 68px; }
.jump.flash { animation: jump-flash 1.6s ease-out; }
@keyframes jump-flash { 0%, 30% { box-shadow: 0 0 0 3px rgba(208,59,59,.35); } 100% { box-shadow: 0 0 0 3px transparent; } }`;
  const style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);
  const nav = document.createElement("nav");
  nav.className = "site-nav";
  nav.setAttribute("aria-label", "宏觀監控儀表板");
  const cur = href => href === here ? ' aria-current="page"' : "";
  nav.innerHTML = `<div class="in"><a class="brand" href="index.html">宏觀監控儀表板</a><div class="tabs">${
    PAGES.map(p => p.items
      ? `<div class="grp${p.items.some(i => i.href === here) ? " current" : ""}"><button type="button" aria-haspopup="true" aria-expanded="false">${p.label}</button><div class="menu">${
          p.items.map(i => `<a href="${i.href}"${cur(i.href)}><b>${i.label}</b><span>${i.desc}</span></a>`).join("")
        }</div></div>`
      : `<a href="${p.href}"${cur(p.href)}>${p.label}</a>`).join("")
  }</div></div>`;
  document.body.prepend(nav);
  // 群組：滑鼠移入即展開（CSS :hover）；觸控／鍵盤點按鈕切換，點外面收起
  const closeAll = except => nav.querySelectorAll(".grp.open").forEach(g => { if (g !== except) {
    g.classList.remove("open"); g.querySelector("button").setAttribute("aria-expanded", "false"); } });
  nav.querySelectorAll(".grp > button").forEach(b => b.addEventListener("click", () => {
    const g = b.parentElement, open = !g.classList.contains("open");
    closeAll(g); g.classList.toggle("open", open); b.setAttribute("aria-expanded", open);
  }));
  document.addEventListener("click", e => { if (!e.target.closest(".site-nav .grp")) closeAll(); });
  document.addEventListener("keydown", e => { if (e.key === "Escape") closeAll(); });

  const jumpTo = (id, smooth = true) => {
    const t = document.getElementById(id);
    if (!t) return;
    const box = t.closest(".card") || t;
    box.classList.add("jump");
    box.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "start" });
    box.classList.remove("flash"); void box.offsetWidth; box.classList.add("flash");
  };
  const jump = el => jumpTo(el.dataset.to);
  // 帶 #id 進頁：圖表資料是非同步載入，版面會長高，等載入後再對齊幾次；使用者自己捲動就停
  const hashId = decodeURIComponent(location.hash.slice(1));
  if (hashId) {
    if ("scrollRestoration" in history) history.scrollRestoration = "manual";
    let userMoved = false;
    const stop = () => { userMoved = true; };
    ["wheel", "touchstart", "keydown", "mousedown"].forEach(ev => addEventListener(ev, stop, { once: true, passive: true }));
    const align = () => { if (userMoved) return; const t = document.getElementById(hashId);
      if (t) (t.closest(".card") || t).scrollIntoView({ block: "start" }); };
    addEventListener("load", () => {
      jumpTo(hashId, false);
      [400, 1000, 2000].forEach(ms => setTimeout(align, ms));
    });
  }
  document.addEventListener("click", e => { const el = e.target.closest(".signal[data-to]"); if (el) jump(el); });
  document.addEventListener("keydown", e => {
    const el = e.target.closest && e.target.closest(".signal[data-to]");
    if (el && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); jump(el); }
  });
})();
