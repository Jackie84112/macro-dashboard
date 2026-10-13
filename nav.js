// 宏觀監控儀表板：共用頂部目錄欄。新增子頁面時在 PAGES 加一列即可。
// 另含共用「點燈號跳轉」：燈號元素寫 class="signal" data-to="目標 id" role="link" tabindex="0"，
// 點擊（或 Enter／空白鍵）平滑捲到目標所在的 .card（無 .card 則目標本身），並閃一下紅框。
(() => {
  const PAGES = [
    { href: "index.html", label: "就業狀況" },
    { href: "margin.html", label: "融資槓桿" },
    { href: "datacenter.html", label: "資料中心成本" },
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

  const jump = el => {
    const t = document.getElementById(el.dataset.to);
    if (!t) return;
    const box = t.closest(".card") || t;
    box.classList.add("jump");
    box.scrollIntoView({ behavior: "smooth", block: "start" });
    box.classList.remove("flash"); void box.offsetWidth; box.classList.add("flash");
  };
  document.addEventListener("click", e => { const el = e.target.closest(".signal[data-to]"); if (el) jump(el); });
  document.addEventListener("keydown", e => {
    const el = e.target.closest && e.target.closest(".signal[data-to]");
    if (el && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); jump(el); }
  });
})();
