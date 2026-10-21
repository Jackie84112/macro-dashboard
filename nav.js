// 宏觀監控儀表板：共用頂部目錄欄。新增子頁面時在 PAGES 加一列即可。
// 改了本檔要同步把各頁 <script src="nav.js?v=…"> 的版本號改新（GitHub Pages 快取 10 分鐘，舊 nav.js 會配到新頁面）
// 另含共用「點燈號跳轉」：燈號元素寫 class="signal" data-to="目標 id" role="link" tabindex="0"，
// 點擊（或 Enter／空白鍵）平滑捲到目標所在的 .card（無 .card 則目標本身），並閃一下紅框。
// 跨頁跳轉：連結寫 頁面.html#目標id（如 rates.html#chart-oil），進頁後同樣捲到該卡片並閃框。
(() => {
  const PAGES = [
    { href: "rates.html", label: "貨幣成本" },
    { href: "index.html", label: "就業狀況" },
    { href: "margin.html", label: "融資槓桿" },
    { href: "datacenter.html", label: "資料中心成本" },
    { href: "risk-chain.html", label: "風險傳導鏈" },
    { href: "asml.html", label: "ASML產能分配" },
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
.site-nav a:focus-visible { outline: 2px solid #E8B04A; outline-offset: -2px; }
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
  nav.innerHTML = `<div class="in"><a class="brand" href="index.html">宏觀監控儀表板</a><div class="tabs">${
    PAGES.map(p => `<a href="${p.href}"${p.href === here ? ' aria-current="page"' : ""}>${p.label}</a>`).join("")
  }</div></div>`;
  document.body.prepend(nav);

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
