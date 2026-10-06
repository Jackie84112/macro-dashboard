// 宏觀監控儀表板：共用頂部目錄欄。新增子頁面時在 PAGES 加一列即可。
(() => {
  const PAGES = [
    { href: "index.html", label: "就業狀況" },
    { href: "margin.html", label: "融資槓桿" },
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
.site-nav a:focus-visible { outline: 2px solid #E8B04A; outline-offset: -2px; }`;
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
})();
