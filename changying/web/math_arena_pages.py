"""数学知识地图与应试专项学生端页面（与主界面宣纸暖白 + 长缨绛红风格完全一致，纯 ES5，无 innerHTML）."""
from __future__ import annotations

from changying.web.arena_role_hub import ARENA_ROLE_HUB_JS
from changying.web.cube_figures_js import CUBES_JS
from changying.web.v1_nezha_icons import AVATAR_PNG_B64
from changying.web.weekend_pages import _page

ARENA_CSS = """<style>
:root{--ma-bg:#faf6f1;--ma-card:#ffffff;--ma-line:#e6d8ce;--ma-ink:#242026;--ma-muted:#65595a;--ma-brand:#a8101c;--ma-brand-dark:#7d0c15;--ma-brand-soft:#fdf1f0;--ma-ok:#0b8f5a;--ma-ok-soft:#e8f8f0;--ma-gold:#b45309;--ma-gold-soft:#fef7e6;--ma-blue:#1e4e79;--ma-blue-soft:#eef5fb;--ma-purple:#6d3b7d;--ma-purple-soft:#f6eff9;--ma-shadow:0 2px 0 #e6d8ce,0 8px 22px rgba(56,28,24,.06)}
@keyframes maFade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}

html,body{background:linear-gradient(180deg,#fcf9f5 0%,#f5eee6 100%)!important;color:var(--ma-ink)!important;margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei","Segoe UI",sans-serif!important}
main,#app{max-width:940px!important;margin:0 auto!important;padding:14px 14px 104px!important;background:transparent!important;box-shadow:none!important;border:0!important}
.ma-wrap{display:flex;flex-direction:column;gap:14px}

/* 顶栏：与主界面一致的克制微立体白卡 */
.ma-topbar{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;background:var(--ma-card);border:1px solid var(--ma-line);border-radius:16px;padding:10px 14px;box-shadow:var(--ma-shadow)}
.ma-topbar-left,.ma-topbar-right{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.ma-seg{display:inline-flex;background:#f4ece4;border-radius:11px;padding:3px;gap:3px;box-shadow:inset 0 1px 2px rgba(56,28,24,.08)}
.ma-seg a{padding:6px 15px;border-radius:9px;text-decoration:none;font-size:14px;font-weight:700;color:var(--ma-muted);transition:all .15s ease}
.ma-seg a.on{background:var(--ma-brand);color:#fff;box-shadow:0 2px 0 var(--ma-brand-dark)}
.ea-subj{display:inline-flex;background:#efe6dc;border-radius:10px;padding:3px;gap:3px;box-shadow:inset 0 1px 2px rgba(56,28,24,.08)}
.ea-subj a{padding:5px 12px;border-radius:8px;text-decoration:none;font-size:13px;font-weight:800;color:var(--ma-muted);transition:all .15s ease}
.ea-subj a.on{background:#fff;color:var(--ma-brand);box-shadow:0 1px 3px rgba(56,28,24,.12)}
.ma-link-btn{display:inline-flex;align-items:center;gap:4px;padding:6px 12px;border-radius:10px;border:1px solid var(--ma-line);background:#fff;color:var(--ma-ink);font-size:13px;font-weight:700;text-decoration:none;cursor:pointer;font-family:inherit;box-shadow:0 2px 0 #eadfd5}
.ma-link-btn:hover{background:#fcf8f3}
.ma-link-btn:active{transform:translateY(1px);box-shadow:0 1px 0 #eadfd5}
.ma-pts{padding:5px 12px;border-radius:999px;background:var(--ma-brand-soft);border:1px solid #f2c6c2;color:var(--ma-brand);font-size:13px;font-weight:800;box-shadow:0 1px 0 #f2c6c2}
.ma-user-pill{display:inline-flex;align-items:center;gap:4px;padding:5px 11px;border-radius:999px;background:#f7f1ea;border:1px solid var(--ma-line);color:var(--ma-ink);font-size:12.5px;font-weight:700;white-space:nowrap}

/* 主副标题层级 */
.ma-eyebrow{font-size:11.5px;font-weight:800;letter-spacing:.06em;color:var(--ma-brand);text-transform:uppercase;margin:0 0 4px}
.ma-h1{margin:0 0 4px;font-size:21px;font-weight:900;color:var(--ma-ink);letter-spacing:-.01em;line-height:1.25}
.ma-sub{margin:0;font-size:13px;color:var(--ma-muted);line-height:1.55}

/* 克制立体按钮 */
.ma-btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;padding:9px 18px;border-radius:11px;border:1px solid transparent;font-size:14px;font-weight:700;cursor:pointer;text-decoration:none;font-family:inherit;transition:transform .1s ease,box-shadow .1s ease,background .15s ease}
.ma-btn:disabled{opacity:.55;cursor:not-allowed}
.ma-btn-primary{background:linear-gradient(180deg,#b81421 0%,#a8101c 100%);color:#fff;box-shadow:0 3px 0 var(--ma-brand-dark)}
.ma-btn-primary:hover:not(:disabled){background:linear-gradient(180deg,#a8101c 0%,#8f0d18 100%)}
.ma-btn-primary:active:not(:disabled){transform:translateY(2px);box-shadow:0 1px 0 var(--ma-brand-dark)}
.ma-btn-ok{background:linear-gradient(180deg,#0fa368 0%,#0b8f5a 100%);color:#fff;box-shadow:0 3px 0 #076942}
.ma-btn-ghost{background:#fff;color:var(--ma-ink);border-color:var(--ma-line);box-shadow:0 2px 0 #e6d8ce}
.ma-btn-ghost:hover:not(:disabled){background:#fcf8f3}
.ma-btn-ghost:active:not(:disabled){transform:translateY(1px);box-shadow:0 1px 0 #e6d8ce}
.ma-btn-sm{padding:6px 12px;font-size:13px;border-radius:9px}

/* 通用清爽微立体白卡 */
.ma-card{background:var(--ma-card);border:1px solid var(--ma-line);border-radius:16px;padding:16px 18px;box-shadow:var(--ma-shadow)}
.ma-card h2{margin:0 0 4px;font-size:19px;font-weight:800;color:var(--ma-ink)}
.ma-card h3{margin:0 0 6px;font-size:16px;font-weight:800;color:var(--ma-ink)}
.ma-muted{color:var(--ma-muted);font-size:13px;margin:0;line-height:1.55}
.ma-notice{padding:10px 14px;border-radius:12px;font-size:13.5px;font-weight:600;display:none}
.ma-notice.show{display:block;animation:maFade .18s ease}
.ma-notice.info{background:#f4f1ec;color:var(--ma-ink);border:1px solid var(--ma-line)}
.ma-notice.warn{background:var(--ma-brand-soft);color:var(--ma-brand);border:1px solid #f2c6c2}

/* 进度概览条 */
.ma-sum-top{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-wrap:wrap}
.ma-sum-meta{display:flex;gap:14px;flex-wrap:wrap;font-size:13px;color:var(--ma-muted);margin-top:8px}
.ma-sum-meta b{color:var(--ma-ink)}
.ma-prog-track{margin-top:10px;height:9px;background:#efe7de;border-radius:999px;overflow:hidden;box-shadow:inset 0 1px 2px rgba(56,28,24,.1)}
.ma-prog-fill{height:100%;background:linear-gradient(90deg,#a8101c 0%,#d9534f 100%);border-radius:999px;transition:width .4s ease}

/* 知识地图：四域双列东方色系微立体卡片 */
.ma-domains{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;align-items:start}
@media(max-width:720px){.ma-domains{grid-template-columns:1fr}}
.ma-domain{background:var(--ma-card);border:1px solid var(--ma-line);border-top:4px solid var(--ma-brand);border-radius:16px;padding:14px 16px;box-shadow:var(--ma-shadow)}
.ma-domain.dom-D1{border-top-color:var(--ma-brand)}
.ma-domain.dom-D2{border-top-color:var(--ma-blue)}
.ma-domain.dom-D3{border-top-color:var(--ma-purple)}
.ma-domain.dom-D4{border-top-color:var(--ma-gold)}
.ma-domain-h{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:10px;padding-bottom:9px;border-bottom:1px solid #f1e8df}
.ma-domain-h h3{margin:0;font-size:16px;font-weight:800;color:var(--ma-ink)}
.ma-domain-sub{font-size:12px;color:var(--ma-muted);margin-top:2px}
.ma-domain-cnt{padding:2px 9px;border-radius:999px;font-size:12px;font-weight:700;background:#f5efe8;color:var(--ma-muted);white-space:nowrap}
.ma-domain.dom-D1 .ma-domain-cnt{background:var(--ma-brand-soft);color:var(--ma-brand)}
.ma-domain.dom-D2 .ma-domain-cnt{background:var(--ma-blue-soft);color:var(--ma-blue)}
.ma-domain.dom-D3 .ma-domain-cnt{background:var(--ma-purple-soft);color:var(--ma-purple)}
.ma-domain.dom-D4 .ma-domain-cnt{background:var(--ma-gold-soft);color:var(--ma-gold)}
.ma-nodes{display:flex;flex-direction:column;gap:7px}
.ma-node{display:flex;justify-content:space-between;align-items:center;gap:10px;width:100%;text-align:left;padding:10px 12px;border-radius:11px;border:1px solid #ede4db;background:#fcfaf7;cursor:pointer;font:inherit;box-shadow:0 1px 0 #ede4db;transition:transform .12s ease,border-color .15s ease,box-shadow .15s ease,background .15s ease}
.ma-node:hover{border-color:var(--ma-brand);background:#fff;transform:translateY(-1px);box-shadow:0 3px 8px rgba(56,28,24,.07)}
.ma-node.sel{border-color:var(--ma-brand);background:var(--ma-brand-soft);box-shadow:0 2px 0 #e8b8b4}
.ma-node.st-lit{border-color:#b7e4cf;background:#f7fcf9}
.ma-node.st-mastered{border-color:#e9c98a;background:#fffdf6}
.ma-node.repair{border-color:#e89b96;background:var(--ma-brand-soft)}
.ma-node.review-due{border-color:#e5a93c;background:linear-gradient(180deg,#fffcf3 0%,#fef6e2 100%);box-shadow:0 1px 0 #ebd19a}
.ma-node-left{display:flex;align-items:center;gap:8px;min-width:0}
.ma-node-right{display:inline-flex;align-items:center;gap:5px;flex-wrap:wrap;justify-content:flex-end;flex-shrink:0}
.ma-node-key{font-size:11.5px;font-weight:800;padding:2px 6px;border-radius:6px;background:#efe8e0;color:var(--ma-muted);flex-shrink:0}
.ma-node-name{font-size:14px;font-weight:700;color:var(--ma-ink);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ma-tag{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;font-weight:700;white-space:nowrap}
.ma-tag.unexplored{background:#efeae4;color:var(--ma-muted)}
.ma-tag.exploring{background:#fef3c7;color:#92400e}
.ma-tag.lit{background:var(--ma-ok-soft);color:var(--ma-ok)}
.ma-tag.mastered{background:var(--ma-gold-soft);color:var(--ma-gold)}
.ma-tag.repair{background:#fee2e2;color:var(--ma-brand)}
.ma-tag.review-due{background:#fef3c7;color:#b45309;border:1px solid #f5cb75}
.ma-task-badge{display:inline-block;padding:2px 7px;border-radius:999px;font-size:11px;font-weight:800;background:#fff1e0;color:#c2410c;border:1px solid #f6bd84;white-space:nowrap}

/* 老师布置的今日任务置顶条 */
.ma-task-banner{background:linear-gradient(180deg,#fff9f2 0%,#fff3e6 100%);border:1.5px solid #f0b878;border-radius:16px;padding:13px 16px;box-shadow:var(--ma-shadow);animation:maFade .2s ease}
.ma-task-banner-h{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px;flex-wrap:wrap}
.ma-task-banner-title{font-size:14.5px;font-weight:900;color:#9a3412;display:inline-flex;align-items:center;gap:6px}
.ma-task-list{display:flex;flex-direction:column;gap:8px}
.ma-task-item{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;padding:9px 12px;border-radius:11px;background:#fff;border:1px solid #f3d5b5}
.ma-task-info{flex:1;min-width:180px}
.ma-task-name{font-size:14px;font-weight:800;color:var(--ma-ink)}
.ma-task-meta{font-size:12px;color:var(--ma-muted);margin-top:2px}

/* 微测老师精选徽章 */
.ma-custom-badge{display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:999px;background:#fef3c7;color:#92400e;border:1px solid #f5c96b;font-size:12px;font-weight:800;margin-bottom:8px}

/* 选中节点底部吸底操作条 */
.ma-detail-dock{position:sticky;bottom:12px;z-index:25}
.ma-detail-dock:empty{display:none}
.ma-detail{position:relative;display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap;animation:maFade .18s ease;border-color:#e2c6be;box-shadow:0 6px 24px rgba(56,28,24,.14),0 2px 0 #e2c6be}
.ma-detail-info{flex:1;min-width:220px;padding-right:62px}
.ma-detail-close{position:absolute;top:10px;right:10px;display:inline-flex;align-items:center;justify-content:center;gap:2px;padding:3px 9px;border-radius:999px;border:1px solid var(--ma-line);background:#fcf8f3;color:var(--ma-muted);font-size:12px;font-weight:700;cursor:pointer;font-family:inherit;line-height:1.4}
.ma-detail-close:hover{background:var(--ma-brand-soft);color:var(--ma-brand);border-color:#efc0bc}
@media(max-width:480px){main,#app{padding:10px 10px 92px!important}.ma-detail-dock{bottom:8px}.ma-detail{padding:11px 12px!important;gap:8px;max-height:38vh;overflow-y:auto}.ma-detail-info{min-width:0;padding-right:54px}.ma-detail h3{font-size:14.5px}.ma-detail .ma-muted{font-size:12px;line-height:1.45}.ma-detail .ma-btn{width:100%;padding:8px 12px;font-size:13.5px}.ma-detail-close{top:8px;right:8px;padding:2px 8px;font-size:11.5px}}

/* 应试专项卡片 */
.ma-sprints{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
@media(max-width:720px){.ma-sprints{grid-template-columns:1fr}}
.ma-sprint{background:var(--ma-card);border:1px solid var(--ma-line);border-radius:16px;padding:16px 18px;box-shadow:var(--ma-shadow);display:flex;flex-direction:column;justify-content:space-between;gap:12px}
.ma-sprint-tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
.ma-pill{padding:2px 8px;border-radius:8px;background:#f5efe8;color:var(--ma-muted);font-size:12px;font-weight:600}

/* 作答区（单题专注 + 顶部简洁计时条） */
.ma-hud{position:sticky;top:8px;z-index:10;background:var(--ma-card);border:1px solid var(--ma-line);border-radius:14px;padding:12px 16px;box-shadow:var(--ma-shadow)}
.ma-hud.urgent{border-color:var(--ma-brand);background:var(--ma-brand-soft)}
.ma-hud-top{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
.ma-clock{font-size:17px;font-weight:800;color:var(--ma-brand)}
.ma-sheet{display:flex;gap:6px;flex-wrap:wrap;align-items:center;background:var(--ma-card);border:1px solid var(--ma-line);border-radius:12px;padding:10px 12px}
.ma-dot{position:relative;min-width:34px;height:32px;border-radius:8px;border:1px solid var(--ma-line);background:#fcfaf7;color:var(--ma-ink);font-weight:700;font-size:13px;cursor:pointer;padding:0 6px}
.ma-dot.done{background:var(--ma-ok-soft);border-color:#93d6b8;color:var(--ma-ok)}
.ma-dot.cur{background:var(--ma-brand);border-color:var(--ma-brand);color:#fff}
.ma-dot-fig{position:absolute;top:2px;right:2px;width:5px;height:5px;border-radius:50%;background:#d97706}
.ma-q-card{background:var(--ma-card);border:1px solid var(--ma-line);border-radius:16px;padding:18px;box-shadow:var(--ma-shadow);animation:maFade .18s ease}
.ma-q-meta{display:flex;justify-content:space-between;gap:8px;font-size:12.5px;color:var(--ma-muted);margin-bottom:8px}
.ma-q-text{font-size:16px;font-weight:700;line-height:1.65;margin:0 0 14px;color:var(--ma-ink)}
.ma-fig-box{background:#fcfaf7;border:1px solid #ede4db;border-radius:12px;padding:12px;margin-bottom:14px;text-align:center;overflow-x:auto}
.ma-fig-box svg{max-width:100%;height:auto}
.ma-opts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
@media(max-width:600px){.ma-opts{grid-template-columns:1fr}}
.ma-opt{display:flex;align-items:center;gap:10px;text-align:left;padding:12px 14px;border-radius:12px;border:1.5px solid var(--ma-line);background:#fff;color:var(--ma-ink);font-size:14.5px;font-weight:600;cursor:pointer;font-family:inherit}
.ma-opt:hover{border-color:var(--ma-brand);background:#fffafa}
.ma-opt.picked{border-color:var(--ma-brand);background:var(--ma-brand-soft);color:var(--ma-brand-dark)}
.ma-opt-k{width:24px;height:24px;border-radius:7px;background:#f4ece4;color:var(--ma-muted);display:inline-flex;align-items:center;justify-content:center;font-size:12.5px;font-weight:800;flex-shrink:0}
.ma-opt.picked .ma-opt-k{background:var(--ma-brand);color:#fff}
.ma-input{width:100%;max-width:340px;padding:11px 13px;border-radius:11px;border:1.5px solid var(--ma-line);background:#fff;font-size:15px;font-weight:600;color:var(--ma-ink);box-sizing:border-box}
.ma-input:focus{outline:none;border-color:var(--ma-brand)}
.ma-foot{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin-top:16px;padding-top:12px;border-top:1px solid #f1e8df}
.ma-confirm{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;padding:10px 14px;border-radius:12px;background:var(--ma-brand-soft);border:1px solid #f2c6c2;color:var(--ma-brand-dark);font-size:13.5px;font-weight:600}
.ma-res-head{text-align:center;padding:20px 16px}
.ma-res-tier{display:inline-block;padding:4px 14px;border-radius:999px;background:var(--ma-brand-soft);color:var(--ma-brand);font-size:14px;font-weight:800;margin-bottom:8px}
.ma-pts-gain{display:inline-block;margin-top:10px;padding:6px 14px;border-radius:10px;background:var(--ma-ok-soft);color:var(--ma-ok);font-size:13.5px;font-weight:700}
.ma-rev{padding:9px 12px;border-radius:10px;font-size:13.5px;line-height:1.55;margin-top:6px}
.ma-rev.ok{background:var(--ma-ok-soft);color:#065f46}
.ma-rev.bad{background:var(--ma-brand-soft);color:var(--ma-brand-dark)}
.ma-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.ma-loss-row{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;padding:8px 0;border-bottom:1px solid #f1e8df}
.ma-loss-row:last-child{border-bottom:0}
/* 长缨助手对话提示条（与主界面宣纸绛红风格统一） */
.ma-helper{display:flex;align-items:center;gap:12px;background:#fffaf6;border:1px solid #ead8cb;border-radius:14px;padding:10px 14px;box-shadow:var(--ma-shadow);animation:maFade .2s ease}
.ma-helper-ava{width:42px;height:42px;border-radius:50%;border:2px solid var(--ma-brand);background:#fff;object-fit:cover;flex-shrink:0}
.ma-helper-body{flex:1;min-width:0}
.ma-helper-name{font-size:12px;font-weight:800;color:var(--ma-brand);margin-bottom:2px}
.ma-helper-text{font-size:13.5px;color:var(--ma-ink);line-height:1.5;margin:0}

/* 3～6年级切换横条与分学段交互样式（语数英三科通用） */
.ma-grade-bar{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;background:var(--ma-card);border:1px solid var(--ma-line);border-radius:14px;padding:9px 14px;box-shadow:var(--ma-shadow)}
.ma-grade-pills{display:inline-flex;align-items:center;gap:6px;flex-wrap:wrap}
.ma-grade-pill{display:inline-flex;align-items:center;gap:5px;padding:6px 12px;border-radius:10px;border:1px solid #eadfd5;background:#fcfaf7;color:var(--ma-ink);font-size:13px;font-weight:800;cursor:pointer;font-family:inherit;box-shadow:0 2px 0 #eadfd5;transition:all .14s ease}
.ma-grade-pill:hover{border-color:var(--ma-brand);background:#fff}
.ma-grade-pill.on,.ma-grade-pill.on:hover{background:var(--ma-brand)!important;border-color:var(--ma-brand)!important;color:#fff!important;box-shadow:0 2px 0 var(--ma-brand-dark)!important}
.ma-grade-rel{display:inline-block;padding:1px 6px;border-radius:999px;font-size:10.5px;font-weight:800;background:#efe8e0;color:var(--ma-muted)}
.ma-grade-pill.on .ma-grade-rel{background:rgba(255,255,255,.24)!important;color:#fff!important}
.ma-grade-rel.current{background:var(--ma-ok-soft);color:var(--ma-ok)}
.ma-grade-rel.review{background:var(--ma-gold-soft);color:var(--ma-gold)}
.ma-grade-rel.advance{background:var(--ma-blue-soft);color:var(--ma-blue)}
.ma-age-badge{display:inline-flex;align-items:center;gap:5px;padding:4px 11px;border-radius:999px;background:#fcf6ef;border:1px solid #ead8cb;color:var(--ma-muted);font-size:12px;font-weight:700}

/* 题干旁语音伴读按钮（G3/G4 友好） */
.ma-q-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin-bottom:14px}
.ma-q-head .ma-q-text{margin:0;flex:1}
.ma-read-btn{display:inline-flex;align-items:center;gap:5px;padding:7px 13px;border-radius:11px;border:1.5px solid #efc0bc;background:var(--ma-brand-soft);color:var(--ma-brand);font-size:13.5px;font-weight:800;cursor:pointer;font-family:inherit;flex-shrink:0;box-shadow:0 2px 0 #efc0bc;transition:all .12s ease}
.ma-read-btn:hover{background:#fbe4e2;transform:translateY(-1px)}
.ma-read-btn:active{transform:translateY(1px);box-shadow:0 1px 0 #efc0bc}

/* G3/G4 数学内嵌大号数字与分数软键盘 */
.ma-keypad{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;max-width:340px;margin-top:10px;padding:10px;border-radius:13px;background:#fcf8f3;border:1px solid #ead8cb}
.ma-keypad.compact{display:flex;flex-wrap:wrap;gap:6px;max-width:360px;padding:7px 9px}
.ma-key{display:inline-flex;align-items:center;justify-content:center;min-height:42px;padding:6px 12px;border-radius:10px;border:1.5px solid var(--ma-line);background:#fff;color:var(--ma-ink);font-size:16px;font-weight:800;cursor:pointer;font-family:inherit;box-shadow:0 2px 0 #e6d8ce;user-select:none;transition:all .1s ease}
.ma-keypad.compact .ma-key{min-height:34px;font-size:13.5px;padding:4px 11px}
.ma-key:hover{border-color:var(--ma-brand);background:#fffafa}
.ma-key:active{transform:translateY(1px);box-shadow:0 1px 0 #e6d8ce}
.ma-key.fn{background:#f5efe8;font-size:13.5px;color:var(--ma-muted)}

/* G3 启蒙模式：题干字号与选项触控间距放大 */
.ma-age-g3 .ma-q-text{font-size:17.5px;line-height:1.72}
.ma-age-g3 .ma-opt{padding:14px 16px;font-size:15.5px}
.ma-age-g3 .ma-read-btn{padding:8px 15px;font-size:14.5px}

/* G1/G2 低段零打字启蒙与积木工作台样式 */
.ma-age-g12 .ma-q-text{font-size:18.5px;line-height:1.75}
.ma-age-g12 .ma-opt{padding:15px 16px;font-size:16px;border-radius:14px}
.ca-block-workbench{padding:12px 14px;border-radius:13px;background:#fffaf2;border:1.5px solid #f2d2a9;margin-bottom:10px}
.ca-block-chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
.ca-block-chip{padding:8px 13px;border-radius:11px;border:1.5px solid #e6c594;background:#fff;color:var(--ma-ink);font-size:14.5px;font-weight:700;cursor:pointer;font-family:inherit;box-shadow:0 2px 0 #ead8cb}
.ca-block-chip:hover{border-color:var(--ma-brand);background:var(--ma-brand-soft);color:var(--ma-brand-dark)}
</style>"""

COMMON_ARENA_JS = r"""
function maRenderRoleOverview(role){
  root.textContent='';
  var isTeacher=(role==='teacher'||role==='admin');
  var backHref=isTeacher?'/v1':'/classic?legacy=1&unified=1&page=parent';
  var backText=isTeacher?'‹ 返回工作台':'‹ 返回家长端';
  var bar=el('div',{class:'ma-topbar'},
    el('div',{class:'ma-topbar-left'},
      el('a',{class:'ma-link-btn',href:backHref,text:backText}),
      el('div',{class:'ea-subj'},
        el('a',{href:'/v1/math-star-map',class:'on',text:'数学'}),
        el('a',{href:'/v1/english-star-map',text:'英语'}),
        el('a',{href:'/v1/chinese-star-map',text:'语文'}))),
    el('div',{class:'ma-topbar-right'},el('span',{class:'ma-pts',text:isTeacher?'教师学情总览':'家长学情视图'})));
  var box=el('div',{class:'ma-wrap'},bar);
  root.appendChild(box);
  var url=isTeacher?'/teacher/math-arena/overview':'/parent/math-arena/children';
  api(url).then(function(d){
    box.appendChild(el('div',{class:'ma-card'},
      el('div',{class:'ma-eyebrow',text:'小学数学 · 知识地图与应试专项'}),
      el('h2',{class:'ma-h1',text:isTeacher?'全班数学闯关与应试学情':'孩子数学闯关与应试学情'}),
      el('p',{class:'ma-sub',text:'覆盖 '+d.totalNodes+' 个通用核心考点与 '+d.totalSprints+' 个限时专项，所有积分同步计入全站账本。'})));
    box.appendChild(maHelperTip(
      isTeacher?'这里汇总了全班学生的地图点亮进度、待修补薄弱点、专项最高段位和全站积分，方便针对性辅导。'
               :'这里同步展示孩子的知识地图点亮情况与应试专项分级结果，重点关注标红的「待修补」考点即可。',
      '长缨助手 · 学情同步'));
    if(!d.items||!d.items.length){
      box.appendChild(el('div',{class:'ma-card'},el('p',{class:'ma-sub',text:isTeacher?'当前学校还没有学生记录。':'暂未关联孩子账号。'})));
      return;
    }
    d.items.forEach(function(it){
      var pct=it.totalNodes?Math.round(it.litNodes/it.totalNodes*100):0;
      var tierTxt=it.bestTier?(it.bestTier.code+' '+it.bestTier.name):'尚未参加专项';
      box.appendChild(el('div',{class:'ma-card'},
        el('div',{class:'ma-sum-top'},
          el('div',{},
            el('h3',{style:'margin:0',text:it.name+(it.grade?'（'+it.grade+'年级）':'')}),
            el('p',{class:'ma-sub',style:'margin-top:3px',text:'已点亮 '+it.litNodes+'/'+it.totalNodes+'（'+pct+'%）· 精通 '+it.masteredNodes+' · 专项最高：'+tierTxt})),
          el('span',{class:'ma-pts',text:'全站积分 '+it.pointsBalance})),
        el('div',{class:'ma-prog-track'},el('div',{class:'ma-prog-fill',style:'width:'+pct+'%'})),
        it.repairNames&&it.repairNames.length
          ?el('p',{class:'ma-sub',style:'margin-top:8px;color:var(--ma-brand)',text:'待修补考点：'+it.repairNames.join('、')})
          :el('p',{class:'ma-sub',style:'margin-top:8px',text:'当前无待修补失分点'})));
    });
  }).catch(function(e){msg(e.message)});
}
function maBoot(run){
  obtainToken().then(function(t){
    TOKEN=t;
    if(!TOKEN){msg('请先登录后再打开');return}
    return api('/session').then(function(s){
      if(s.role==='student'){window.__CY_ARENA_USER__=s;run();return}
      if(s.role==='teacher'||s.role==='admin'||s.role==='parent'){arenaRoleHub(s.role,'数学',s);return}
      msg('当前身份无法访问此页面');
    });
  }).catch(function(e){msg(e.message||'打不开')});
}
function maStars(n){var s='',i;for(i=0;i<n;i++)s+='★';return s}
function maClockText(sec){var s=Math.max(0,Math.floor(sec)),m=Math.floor(s/60),r=s%60;return (m<10?'0':'')+m+':'+(r<10?'0':'')+r}
function maGetActiveGrade(){
  var m=/[?&]grade=([123456])/.exec(location.search||'');
  if(m){window.__CY_ARENA_GRADE__=Number(m[1]);return Number(m[1])}
  if(window.__CY_ARENA_GRADE__&&[1,2,3,4,5,6].indexOf(Number(window.__CY_ARENA_GRADE__))>=0){
    return Number(window.__CY_ARENA_GRADE__);
  }
  var u=window.__CY_ARENA_USER__;
  if(u&&u.grade&&[1,2,3,4,5,6].indexOf(Number(u.grade))>=0)return Number(u.grade);
  return 0;
}
function maSetActiveGrade(g){
  var n=Number(g);
  if([1,2,3,4,5,6].indexOf(n)<0)return;
  window.__CY_ARENA_GRADE__=n;
  if(window.history&&window.history.replaceState){
    try{window.history.replaceState(null,'',location.pathname+'?grade='+encodeURIComponent(n)+(location.hash||''))}catch(_e){}
  }
}
function maInitGrade(){
  var m=/[?&]grade=([123456])/.exec(location.search||'');
  if(m){window.__CY_ARENA_GRADE__=Number(m[1]);return Number(m[1])}
  if(window.__CY_ARENA_GRADE__&&[1,2,3,4,5,6].indexOf(Number(window.__CY_ARENA_GRADE__))>=0)return Number(window.__CY_ARENA_GRADE__);
  return 0;
}
function maGradeQuery(g){
  var gr=g||window.__CY_ARENA_GRADE__||0;
  return gr?('?grade='+encodeURIComponent(gr)):'';
}
function maInferGrade(key,fallback){
  var s=String(key||'').toUpperCase();
  if(s.indexOf('G1-')===0)return 1;
  if(s.indexOf('G2-')===0)return 2;
  if(s.indexOf('G3-')===0)return 3;
  if(s.indexOf('G4-')===0)return 4;
  if(s.indexOf('G5-')===0)return 5;
  if(s.indexOf('G6-')===0)return 6;
  return fallback||5;
}
function maTopbar(active,pts,grade){
  var curGrade=grade||window.__CY_ARENA_GRADE__||0;
  var qStr=maGradeQuery(curGrade);
  var bar=el('div',{class:'ma-topbar'});
  var left=el('div',{class:'ma-topbar-left'},
    el('a',{class:'ma-link-btn',href:'/classic?legacy=1&unified=1&page=practice',text:'‹ 返回练习'}),
    el('div',{class:'ea-subj'},
      el('a',{href:(active==='sprints'?'/v1/math-sprints':'/v1/math-star-map')+qStr,class:'on',text:'数学'}),
      el('a',{href:(active==='sprints'?'/v1/english-sprints':'/v1/english-star-map')+qStr,text:'英语'}),
      el('a',{href:(active==='sprints'?'/v1/chinese-sprints':'/v1/chinese-star-map')+qStr,text:'语文'})));
  var seg=el('div',{class:'ma-seg'},
    el('a',{href:'/v1/math-star-map'+qStr,class:active==='map'?'on':'',text:'知识地图'}),
    el('a',{href:'/v1/math-sprints'+qStr,class:active==='sprints'?'on':'',text:'应试专项'}));
  var right=el('div',{class:'ma-topbar-right'});
  var u=window.__CY_ARENA_USER__;
  if(u&&u.name)right.appendChild(el('span',{class:'ma-user-pill',text:u.name+' · 学生'}));
  if(pts)right.appendChild(el('a',{class:'ma-pts',href:'/classic?legacy=1&unified=1&page=rewards',style:'text-decoration:none',title:'查看全站积分奖励 · 今日学习积分 '+pts.todayEarned+'/'+pts.dailyCap,text:'积分 '+pts.balance+' ›'}));
  bar.appendChild(left);bar.appendChild(seg);bar.appendChild(right);
  return bar;
}
function maRenderGradeBar(data,onSwitch){
  var grades=(data&&data.availableGrades)||[
    {grade:1,label:'一年级',relation:'review',relationLabel:'查漏补缺'},
    {grade:2,label:'二年级',relation:'review',relationLabel:'查漏补缺'},
    {grade:3,label:'三年级',relation:'review',relationLabel:'查漏补缺'},
    {grade:4,label:'四年级',relation:'review',relationLabel:'查漏补缺'},
    {grade:5,label:'五年级',relation:'current',relationLabel:'本年级'},
    {grade:6,label:'六年级',relation:'advance',relationLabel:'超前探索'}
  ];
  var curG=(data&&data.grade)||maGetActiveGrade()||5;
  var prof=(data&&data.ageProfile)||{};
  var pills=el('div',{class:'ma-grade-pills'});
  grades.forEach(function(item){
    var isOn=Number(item.grade)===Number(curG);
    var relCls='ma-grade-rel '+(item.relation||'');
    var btn=el('button',{type:'button',class:'ma-grade-pill'+(isOn?' on':''),'data-grade':String(item.grade),onclick:function(){
      if(Number(item.grade)===Number(curG))return;
      maSetActiveGrade(item.grade);
      if(typeof onSwitch==='function')onSwitch(Number(item.grade));
    }},
      el('span',{text:item.label||(item.grade+'年级')}),
      item.relationLabel?el('span',{class:relCls,text:item.relationLabel}):null);
    pills.appendChild(btn);
  });
  var badgeTxt=prof.tierLabel||prof.tierShortLabel||(curG+'年级适配模式');
  return el('div',{class:'ma-grade-bar'},
    pills,
    el('span',{class:'ma-age-badge',text:'🎯 '+badgeTxt}));
}
function maSpeakStem(text,ageProf){
  if(!window.speechSynthesis||!window.SpeechSynthesisUtterance)return;
  try{window.speechSynthesis.cancel()}catch(_e){}
  var clean=String(text||'')
    .replace(/×/g,' 乘 ')
    .replace(/÷/g,' 除以 ')
    .replace(/=/g,' 等于 ')
    .replace(/_{2,}|（\s*）|\(\s*\)/g,' 括号 ')
    .replace(/\s+/g,' ');
  var u=new window.SpeechSynthesisUtterance(clean);
  u.lang='zh-CN';
  var fallbackRate=(ageProf&&ageProf.tier==='g12_playful')?0.85:0.9;
  u.rate=(ageProf&&ageProf.speechRate)?Number(ageProf.speechRate):fallbackRate;
  try{window.speechSynthesis.speak(u)}catch(_e2){}
}
function maBuildStemRow(q,ageProf){
  var p=el('p',{class:'ma-q-text',text:q.text});
  var canRead=!!(ageProf&&(ageProf.stemReadAloud||ageProf.tier==='g12_playful'||ageProf.tier==='g3_guided'));
  if(!canRead)return p;
  var btn=el('button',{type:'button',class:'ma-read-btn','aria-label':'朗读题干',text:'🔊 读题',onclick:function(){
    var readText=String(q.text||'');
    if(ageProf&&ageProf.optionReadAloud&&q.options&&q.options.length){
      var optParts=[];
      q.options.forEach(function(opt,idx){
        optParts.push(String.fromCharCode(65+idx)+'，'+String(opt));
      });
      readText=readText+' 选项： '+optParts.join('； ');
    }
    maSpeakStem(readText,ageProf);
  }});
  return el('div',{class:'ma-q-head'},p,btn);
}
function maBuildMathKeypad(inp,ageProf,onSync){
  var mode=(ageProf&&ageProf.mathKeypad)||(ageProf&&ageProf.tier==='g12_playful'?'full':'none');
  if(mode!=='full'&&mode!=='compact')return null;
  var keys=mode==='full'
    ?['1','2','3','4','5','6','7','8','9','0','.','/','⌫','清空']
    :['.','/','00','⌫','清空'];
  var pad=el('div',{class:'ma-keypad'+(mode==='compact'?' compact':'')});
  keys.forEach(function(k){
    var isFn=(k==='⌫'||k==='清空');
    var b=el('button',{type:'button',class:'ma-key'+(isFn?' fn':''),text:k==='⌫'?'⌫ 退格':k,onclick:function(){
      var curVal=String(inp.value||'');
      if(k==='清空'){inp.value=''}
      else if(k==='⌫'){inp.value=curVal.slice(0,Math.max(0,curVal.length-1))}
      else if(curVal.length<120){inp.value=curVal+k}
      if(typeof onSync==='function')onSync(inp.value);
    }});
    pad.appendChild(b);
  });
  return pad;
}
function maFetchTasks(subject){
  return api('/student/arena-tasks').catch(function(){
    return api('/student/arena/tasks?subject='+encodeURIComponent(subject));
  }).then(function(r){
    var arr=(r&&r.items)?r.items:[];
    return arr.filter(function(it){
      return (!it.subject||it.subject===subject)&&it.status!=='done';
    });
  }).catch(function(){return []});
}
function maRenderTaskBanner(tasks,onGo){
  if(!tasks||!tasks.length)return null;
  var list=el('div',{class:'ma-task-list'});
  tasks.forEach(function(t){
    var goalTxt=(t.goalLabel||t.goalCode||'完成练习')+(t.isFresh?'（需重新完成）':'');
    var metaTxt='目标：'+goalTxt+(t.dueDate?(' · 截止 '+t.dueDate):'');
    var btn=el('button',{type:'button',class:'ma-btn ma-btn-primary ma-btn-sm',text:'立即前往'});
    btn.onclick=function(){onGo(t)};
    list.appendChild(el('div',{class:'ma-task-item'},
      el('div',{class:'ma-task-info'},
        el('div',{class:'ma-task-name',text:(t.taskKind==='sprint'?'[专项] ':'[考点] ')+(t.targetTitle||t.targetKey)}),
        el('div',{class:'ma-task-meta',text:metaTxt})),
      btn));
  });
  return el('div',{class:'ma-task-banner'},
    el('div',{class:'ma-task-banner-h'},
      el('div',{class:'ma-task-banner-title',text:'📌 老师布置的今日任务（'+tasks.length+' 项待完成）'})),
    list);
}
function maPointsGain(awarded,pts){
  if(!awarded)return null;
  if(awarded.total>0){
    return el('div',{class:'ma-pts-gain',text:'全站积分 +'+awarded.total+' 分'+(pts?'（当前总积分 '+pts.balance+'）':'')});
  }
  if(awarded.capped){
    return el('div',{class:'ma-pts-gain',text:'今日闯关积分已达 30 分上限，本次成绩已正常记录'});
  }
  return null;
}
function maHelperTip(text,tag){
  var src=window.__CY_HELPER_AVATAR__||'';
  return el('div',{class:'ma-helper'},
    src?el('img',{class:'ma-helper-ava',src:src,alt:'长缨助手'}):null,
    el('div',{class:'ma-helper-body'},
      el('div',{class:'ma-helper-name',text:tag||'长缨助手'}),
      el('p',{class:'ma-helper-text',text:text})));
}
function maQuestionHint(q){
  if(!q)return '仔细读题，看清单位和小数点哦！';
  if(q.hasFigure)return '先看清图上的标注与方格数，再列式计算会更稳！';
  if(q.questionType==='error_diagnosis')return '易错辨析题藏着常见小陷阱，先找错在哪里再作答！';
  if(q.questionType==='multi_step')return '综合推理题可以分两步拆开算，别急着口算！';
  if(q.questionType==='calculation')return '计算题算完可以反推验算一遍，稳拿 3 分！';
  if(q.questionType==='short_answer')return '解决问题先找已知条件和数量关系，再算最终结果！';
  return '认真读清题干关键词，选出最有把握的答案！';
}
"""

STAR_MAP_JS = COMMON_ARENA_JS + r"""
var MSM=null,MSEL=null,MTASKS=[],MTOP=null,MSUM=null,MMSG=null,MDETAIL=null,MQUIZ=null,MGRID=null,MMODE='map',MGRADE=maInitGrade();
function mSay(text,bad){
  MMSG.textContent=text||'';
  MMSG.className=text?('ma-notice show '+(bad?'warn':'info')):'ma-notice';
}
function mHasTask(nodeKey){
  var i;
  for(i=0;i<MTASKS.length;i++){
    if(MTASKS[i].taskKind==='map_node'&&MTASKS[i].targetKey===nodeKey)return true;
  }
  return false;
}
function mIsReviewDue(n){
  return !!(n&&(n.reviewDue||(n.light&&n.light.reviewDue)));
}
function mScrollToNode(key){
  var elBtn=MGRID&&MGRID.querySelector('[data-node="'+key+'"]');
  if(elBtn&&elBtn.scrollIntoView)elBtn.scrollIntoView({behavior:'smooth',block:'center'});
}
function mFocusNode(key){
  if(!MSM||!MSM.nodes)return;
  var hit=MSM.nodes.filter(function(x){return x.key===key})[0];
  if(!hit)return;
  MSEL=hit.key;
  mRenderGrid();
  mRenderDetail(hit);
  mScrollToNode(hit.key);
}
function mTag(light){
  if(light.needsRepair)return el('span',{class:'ma-tag repair',text:'待修补'});
  var txt=light.stateLabel+(light.stars?' '+maStars(light.stars):'');
  return el('span',{class:'ma-tag '+light.state,text:txt});
}
function mRenderHeader(){
  var s=MSM.summary,pct=s.totalNodes?Math.round(s.litNodes/s.totalNodes*100):0;
  var revCnt=s.reviewDueCount||0;
  var curGrade=MSM.grade||MGRADE||5;
  window.__CY_ARENA_GRADE__=curGrade;
  MGRADE=curGrade;
  MTOP.textContent='';
  MTOP.appendChild(maTopbar('map',MSM.points,curGrade));
  MSUM.textContent='';
  MSUM.appendChild(maRenderGradeBar(MSM,function(newGrade){
    MGRADE=newGrade;
    mLoad(newGrade);
  }));
  var top=el('div',{class:'ma-sum-top'},
    el('div',{},
      el('div',{class:'ma-eyebrow',text:'小学数学 · '+curGrade+'年级通用基础模块'}),
      el('h2',{class:'ma-h1',text:MSM.title||'知识地图'}),
      el('p',{class:'ma-sub',text:'不限教材版本，覆盖 '+s.totalNodes+' 个核心考点；点任意节点做 5 题微测，答对 80% 即点亮并加积分。'})),
    el('div',{class:'ma-row'},
      s.repairNodes?el('button',{type:'button',class:'ma-btn ma-btn-primary ma-btn-sm',text:'去修补（'+s.repairNodes+'）',onclick:function(){
        var rep=MSM.nodes.filter(function(x){return x.light.needsRepair})[0];
        if(rep){mFocusNode(rep.key)}
      }}):null,
      el('a',{class:'ma-btn ma-btn-ghost ma-btn-sm',href:'/v1/math-sprints'+maGradeQuery(curGrade),text:'去应试专项 ›'})));
  var meta=el('div',{class:'ma-sum-meta'},
    el('span',{},'已点亮 ',el('b',{text:s.litNodes+'/'+s.totalNodes+'（'+pct+'%）'})),
    el('span',{},'精通 ',el('b',{text:String(s.masteredNodes)})),
    el('span',{},'星数 ',el('b',{text:s.totalStars+'/'+s.maxStars})),
    revCnt>0?el('span',{style:'color:#b45309;font-weight:700'},'待温习 ',el('b',{style:'color:#b45309',text:String(revCnt)}),' 个'):null);
  MSUM.appendChild(el('div',{class:'ma-card'},top,meta,el('div',{class:'ma-prog-track'},el('div',{class:'ma-prog-fill',style:'width:'+pct+'%'}))));
  var banner=maRenderTaskBanner(MTASKS,function(t){
    var tGrade=t.grade||maInferGrade(t.targetKey,curGrade);
    if(t.taskKind==='map_node'){
      if(Number(tGrade)!==Number(curGrade)){
        MGRADE=Number(tGrade);window.__CY_ARENA_GRADE__=Number(tGrade);
        location.hash='#node='+encodeURIComponent(t.targetKey);
        mLoad(MGRADE);
      }else{
        mFocusNode(t.targetKey);
      }
    }else{
      location.href='/v1/math-sprints?grade='+encodeURIComponent(tGrade)+'#sprint='+encodeURIComponent(t.targetKey);
    }
  });
  if(banner)MSUM.appendChild(banner);
  var tipText=revCnt>0
    ?('你有 '+revCnt+' 个已点亮考点快遗忘了，先点琥珀色「需温习」节点做 5 题保鲜吧！'+(s.repairNodes?' 另外还有 '+s.repairNodes+' 个红色「待修补」考点也别忘了哦！':''))
    :(s.repairNodes
      ?('你有 '+s.repairNodes+' 个考点在应试专项里丢过分，点红色「待修补」节点做 5 题，修好立刻消除红标并 +2 积分！')
      :(s.litNodes===0
        ?'欢迎来到'+curGrade+'年级数学知识地图！先挑一个熟悉的考点做 5 道微测，答对 4 题就能点亮第一颗星并获得 +3 全站积分。'
        :(s.litNodes<s.totalNodes
          ?'已经点亮 '+s.litNodes+' 个考点啦！继续攻克未点亮节点，全部点亮后去应试专项冲刺 L4 钻章吧！'
          :'太厉害了，全部 '+s.totalNodes+' 个数学核心考点已点亮！去应试专项刷满 L4 冲刺段位吧！')));
  MSUM.appendChild(maHelperTip(tipText,'长缨助手 · 学习建议'));
}
var DOM_SUBS_BY_GRADE={
  1:{D1:'10以内分合、11～20十位个位、100以内数序与整十数加一位数',D2:'10以内口算、20以内凑十法进位加、破十法退位减与两位数口算',D3:'上下前后左右位置、立体图形积木、平面图形拼组与整时人民币',D4:'一图四式求和求部分、比多少应用、找规律填数与排队问题'},
  2:{D1:'100以内进位加退位减、连加连减混合与2～9表内乘法口诀',D2:'平均分与除法初步、用乘法口诀求商、有余数除法与万以内数',D3:'厘米和米测量、直角锐角钝角、观察物体对称平移旋转与时分克千克',D4:'乘加乘减两级混合运算、有余数租船周期、排列搭配与方格逻辑推理'},
  3:{D1:'万以内加减法验算、多位数乘一位数、一位数除法与两位数乘两位数',D2:'毫米分米千米、吨与千克换算、长方形与正方形周长面积',D3:'四则混合运算、两步应用题、分数与一位小数初步认识',D4:'时分秒与经过时间、年月日与24时计时法、复式统计表与集合重叠'},
  4:{D1:'大数的认识与近似数、三位数乘两位数、除数是两位数除法与运算律',D2:'公顷与平方千米、角的度量、平行四边形梯形与三角形内角和',D3:'小数的意义性质、小数加减法、单价速度模型与烙饼沏茶统筹',D4:'条形统计图、平均数与复式条形图、鸡兔同笼与和差倍问题'},
  5:{D1:'小数乘除、简便运算、因数倍数与分数加减',D2:'图形运动、多边形面积、数对位置与长方体体积',D3:'字母与方程、分段计费、进一去尾、植树与找次品',D4:'确定与随机事件、可能性公平性与折线统计图'},
  6:{D1:'分数乘除法、比与按比分配、百分数与折扣税率利率',D2:'位置与方向、圆的周长面积、扇形圆环与圆柱圆锥体积',D3:'负数与数轴、解比例、正反比例应用与比例尺放大缩小',D4:'扇形统计图、分数工程问题、数与形规律及鸽巢原理行程压轴'}
};
function mRenderGrid(){
  MGRID.textContent='';
  var curG=(MSM&&MSM.grade)||MGRADE||5;
  var domMap=DOM_SUBS_BY_GRADE[curG]||DOM_SUBS_BY_GRADE[5];
  MSM.units.forEach(function(u){
    var box=el('div',{class:'ma-domain dom-'+u.key});
    box.appendChild(el('div',{class:'ma-domain-h'},
      el('div',{},el('h3',{text:u.name}),el('div',{class:'ma-domain-sub',text:domMap[u.key]||''})),
      el('span',{class:'ma-domain-cnt',text:u.litNodes+'/'+u.totalNodes+' 已点亮'})));
    var list=el('div',{class:'ma-nodes'});
    MSM.nodes.filter(function(n){return n.unit===u.key}).forEach(function(n){
      var isRev=mIsReviewDue(n);
      var hasT=mHasTask(n.key);
      var cls='ma-node st-'+n.light.state+(n.light.needsRepair?' repair':'')+(isRev?' review-due':'')+(MSEL===n.key?' sel':'');
      var rightTags=el('span',{class:'ma-node-right'},
        hasT?el('span',{class:'ma-task-badge',text:'老师任务'}):null,
        isRev?el('span',{class:'ma-tag review-due',text:'需温习'}):null,
        mTag(n.light));
      list.appendChild(el('button',{type:'button',class:cls,'data-node':n.key,onclick:function(){
        MSEL=n.key;mRenderGrid();mRenderDetail(n);
      }},el('span',{class:'ma-node-left'},el('span',{class:'ma-node-key',text:n.key}),el('span',{class:'ma-node-name',text:n.name})),rightTags));
    });
    box.appendChild(list);
    MGRID.appendChild(box);
  });
}
function mRenderDetail(n){
  MDETAIL.textContent='';
  if(!n)return;
  var st=n.light;
  var isRev=mIsReviewDue(n);
  var revDays=n.daysSincePractice||(st&&st.daysSincePractice)||0;
  var info=el('div',{class:'ma-detail-info'},
    el('div',{class:'ma-row'},
      el('h3',{style:'margin:0',text:n.key+' · '+n.name}),
      mHasTask(n.key)?el('span',{class:'ma-task-badge',text:'老师任务'}):null,
      isRev?el('span',{class:'ma-tag review-due',text:'需温习'}):null,
      mTag(st)),
    el('p',{class:'ma-muted',style:'margin-top:4px',text:n.detail}),
    el('p',{class:'ma-muted',style:'margin-top:4px',text:'已测 '+st.attempts+' 题 · 正确率 '+st.accuracy+'%'+(st.needsRepair?' · 该节点在应试专项中丢过分，点亮一次即可消除红标':(isRev?(' · 已 '+revDays+' 天未练习，建议温习保鲜'):''))}));
  var closeBtn=el('button',{type:'button',class:'ma-detail-close','aria-label':'收起详情',text:'× 收起',onclick:function(){
    MSEL=null;MDETAIL.textContent='';mRenderGrid();
  }});
  var act=el('button',{type:'button',class:'ma-btn ma-btn-primary',text:isRev?'温习 5 题保鲜':(st.state==='unexplored'?'开始 5 题微测':'再测 5 题'),onclick:function(){mStartQuiz(n)}});
  MDETAIL.appendChild(el('div',{class:'ma-card ma-detail'},closeBtn,info,act));
}
function mStartQuiz(n){
  mSay('正在准备题目…');
  api('/student/math-star-map/nodes/'+encodeURIComponent(n.key)+'/quiz',{method:'POST'}).then(function(d){
    mSay('');MMODE='quiz';
    MSUM.style.display='none';MDETAIL.style.display='none';MGRID.style.display='none';
    MQUIZ.style.display='';MQUIZ.textContent='';
    var ageProf=d.ageProfile||(MSM&&MSM.ageProfile)||{};
    var qGrade=Number(d.grade||(MSM&&MSM.grade)||MGRADE||5);
    var isG12=(ageProf.tier==='g12_playful'||qGrade===1||qGrade===2);
    var isG3=(ageProf.tier==='g3_guided'||qGrade===3);
    var ageCls=isG12?'ma-age-g12 ma-age-g3':(isG3?'ma-age-g3':'');
    var answers={},cur=0,seq=0;
    var hud=el('div',{class:'ma-hud'}),sheet=el('div',{class:'ma-sheet'}),qWrap=el('div',{class:ageCls});
    MQUIZ.appendChild(el('div',{class:'ma-wrap'},hud,sheet,qWrap));

    function exitQuiz(){
      if(window.speechSynthesis){try{window.speechSynthesis.cancel()}catch(_e){}}
      MMODE='map';MQUIZ.style.display='none';MQUIZ.textContent='';
      MSUM.style.display='';MDETAIL.style.display='';MGRID.style.display='';
    }
    function renderHudAndSheet(){
      var doneCnt=d.questions.filter(function(q){return !!answers[q.id]}).length;
      hud.textContent='';
      hud.appendChild(el('div',{class:'ma-hud-top'},
        el('div',{},el('b',{text:d.nodeKey+' '+d.nodeName}),el('span',{class:'ma-muted',style:'margin-left:10px',text:'已答 '+doneCnt+'/'+d.count+' 题（答对 ≥ 80% 点亮）'})),
        el('button',{type:'button',class:'ma-btn ma-btn-ghost ma-btn-sm',text:'返回地图',onclick:exitQuiz})));
      hud.appendChild(el('div',{class:'ma-prog-track'},el('div',{class:'ma-prog-fill',style:'width:'+Math.round(doneCnt/d.count*100)+'%'})));
      sheet.textContent='';
      sheet.appendChild(el('span',{class:'ma-muted',style:'font-weight:700',text:'题号：'}));
      d.questions.forEach(function(q,idx){
        var dot=el('button',{type:'button',class:'ma-dot'+(idx===cur?' cur':(answers[q.id]?' done':'')),text:String(idx+1),onclick:function(){cur=idx;renderStep()}});
        if(q.hasFigure)dot.appendChild(el('span',{class:'ma-dot-fig'}));
        sheet.appendChild(dot);
      });
    }
    function renderStep(){
      seq++;var mySeq=seq;
      renderHudAndSheet();
      qWrap.textContent='';
      var q=d.questions[cur];
      var card=el('div',{class:'ma-q-card','data-q':q.id},
        el('div',{class:'ma-q-meta'},el('span',{text:'第 '+(cur+1)+' / '+d.count+' 题 · '+q.typeLabel}),el('span',{text:'难度：'+q.levelLabel})),
        q.isCustom?el('div',{class:'ma-custom-badge',text:'★ 老师精选'}):null,
        maBuildStemRow(q,ageProf));
      if(typeof cyIsDrawnFigure==='function'&&cyIsDrawnFigure(q.figure)){
        card.appendChild(el('div',{class:'ma-fig-box'},cyCubeSvgNode(q.figure)));
      }
      if(q.questionType==='single_choice'||q.questionType==='true_false'){
        var opts=el('div',{class:'ma-opts'});
        var qOpts=(q.options&&q.options.length)?q.options:(q.questionType==='true_false'?['正确','错误']:[]);
        qOpts.forEach(function(o,k){
          var picked=answers[q.id]&&answers[q.id].selected_index===k;
          var btn=el('button',{type:'button',class:'ma-opt'+(picked?' picked':''),onclick:function(){
            answers[q.id]={question_id:q.id,selected_index:k};
            renderHudAndSheet();
            Array.prototype.forEach.call(opts.children,function(c){c.className='ma-opt'});
            btn.className='ma-opt picked';
            if(cur<d.questions.length-1){
              setTimeout(function(){if(seq===mySeq){cur++;renderStep()}},200);
            }
          }},el('span',{class:'ma-opt-k',text:String.fromCharCode(65+k)}),el('span',{text:o}));
          opts.appendChild(btn);
        });
        card.appendChild(opts);
      }else{
        var prev=answers[q.id]&&answers[q.id].text_answer?answers[q.id].text_answer:'';
        var inp=el('input',{class:'ma-input','aria-label':'第'+(cur+1)+'题答案',placeholder:'输入答案',maxlength:'120',value:prev});
        function syncInputVal(rawVal){
          var v=String(rawVal||'').trim();
          if(v)answers[q.id]={question_id:q.id,text_answer:v};
          else delete answers[q.id];
          renderHudAndSheet();
        }
        inp.addEventListener('input',function(){syncInputVal(inp.value)});
        card.appendChild(inp);
        var pad=maBuildMathKeypad(inp,ageProf,syncInputVal);
        if(pad)card.appendChild(pad);
      }
      var leftBtns=el('div',{class:'ma-row'});
      if(cur>0)leftBtns.appendChild(el('button',{type:'button',class:'ma-btn ma-btn-ghost ma-btn-sm',text:'上一题',onclick:function(){cur--;renderStep()}}));
      var rightBtns=el('div',{class:'ma-row'});
      if(cur<d.questions.length-1)rightBtns.appendChild(el('button',{type:'button',class:'ma-btn ma-btn-ghost ma-btn-sm',text:'下一题',onclick:function(){cur++;renderStep()}}));
      var send=el('button',{type:'button',class:'ma-btn ma-btn-primary ma-btn-sm',text:'提交微测',onclick:function(){
        var miss=-1,i;
        for(i=0;i<d.questions.length;i++){if(!answers[d.questions[i].id]){miss=i;break}}
        if(miss>=0){cur=miss;renderStep();mSay('第 '+(miss+1)+' 题还未作答',true);return}
        send.disabled=true;mSay('正在判分…');
        api('/student/math-star-map/nodes/'+encodeURIComponent(n.key)+'/quiz/submit',{
          json:{quiz_id:d.quizId,answers:d.questions.map(function(x){return answers[x.id]})}
        }).then(function(r){
          MSM=r.map;mSay('');
          maFetchTasks('数学').then(function(ts){MTASKS=ts;mRenderHeader();mRenderGrid()});
          mRenderHeader();mRenderGrid();
          var upd=MSM.nodes.filter(function(x){return x.key===n.key})[0];
          if(upd){MSEL=upd.key;mRenderDetail(upd)}
          MQUIZ.textContent='';
          var resHead=el('div',{class:'ma-card ma-res-head'},
            el('div',{class:'ma-res-tier',text:r.litUp?(r.repaired?'修补成功 · 红标已消除':'节点已点亮'):'继续加油'}),
            el('h2',{text:'答对 '+r.correct+' / '+r.total+' 题（'+r.accuracy+'%）'}),
            el('p',{class:'ma-muted',text:'当前状态：'+r.light.stateLabel+(r.light.stars?' '+maStars(r.light.stars):'')}),
            maPointsGain(r.pointsAwarded,r.points));
          var rev=el('div',{class:'ma-card'},el('h3',{text:'逐题解析'}));
          r.details.forEach(function(it,idx){
            rev.appendChild(el('div',{class:'ma-rev '+(it.correct?'ok':'bad'),text:(idx+1)+'. '+(it.correct?'正确':'错误（答案：'+it.answer+'）')+' — '+it.explanation}));
          });
          var acts=el('div',{class:'ma-row'},
            el('button',{type:'button',class:'ma-btn ma-btn-primary',text:'再测 5 题',onclick:function(){mStartQuiz(n)}}),
            el('button',{type:'button',class:'ma-btn ma-btn-ghost',text:'返回地图',onclick:exitQuiz}));
          MQUIZ.appendChild(el('div',{class:'ma-wrap'},resHead,rev,acts));
        }).catch(function(e){send.disabled=false;mSay(e.message,true)});
      }});
      rightBtns.appendChild(send);
      card.appendChild(el('div',{class:'ma-foot'},leftBtns,rightBtns));
      qWrap.appendChild(maHelperTip(maQuestionHint(q),'长缨助手 · 解题提示'));
      qWrap.appendChild(card);
    }
    renderStep();
    window.scrollTo(0,0);
  }).catch(function(e){mSay(e.message,true)});
}
function mLoad(reqGrade){
  var g=reqGrade||MGRADE||maInitGrade();
  root.textContent='';
  MTOP=el('div');MSUM=el('div');MMSG=el('div',{class:'ma-notice',role:'status'});
  MQUIZ=el('div',{style:'display:none'});MDETAIL=el('div',{class:'ma-detail-dock'});MGRID=el('div',{class:'ma-domains'});
  root.appendChild(el('div',{class:'ma-wrap'},MTOP,MSUM,MMSG,MQUIZ,MGRID,MDETAIL));
  var url='/student/math-star-map'+(g?('?grade='+encodeURIComponent(g)):'');
  Promise.all([api(url),maFetchTasks('数学')]).then(function(res){
    MSM=res[0];MTASKS=res[1]||[];
    if(MSM&&MSM.grade){MGRADE=MSM.grade;window.__CY_ARENA_GRADE__=MSM.grade}
    mRenderHeader();mRenderGrid();
    var want=/[#&]node=([^&]+)/.exec(location.hash);
    var wantKey=want?decodeURIComponent(want[1]):'';
    if(wantKey&&!MSM.nodes.filter(function(x){return x.key===wantKey})[0]){
      var inferred=maInferGrade(wantKey,0);
      if(inferred&&inferred!==Number(MSM.grade)){
        MGRADE=inferred;window.__CY_ARENA_GRADE__=inferred;
        mLoad(inferred);return;
      }
    }
    var hit=wantKey&&MSM.nodes.filter(function(x){return x.key===wantKey})[0];
    var pick=hit||MSM.nodes.filter(function(x){return x.light.needsRepair})[0]||MSM.nodes[0];
    if(pick){
      MSEL=pick.key;mRenderGrid();mRenderDetail(pick);
      if(hit)mScrollToNode(hit.key);
    }
  }).catch(function(e){msg(e.message)});
}
maBoot(mLoad);
"""

SPRINTS_JS = COMMON_ARENA_JS + r"""
var SPTIMER=null,SPTOP=null,SPMSG=null,SPBOX=null,SPGRADE=maInitGrade(),SPDATA=null;
function spSay(text,bad){
  SPMSG.textContent=text||'';
  SPMSG.className=text?('ma-notice show '+(bad?'warn':'info')):'ma-notice';
}
function spClearTimer(){if(SPTIMER){clearInterval(SPTIMER);SPTIMER=null}}
function spLoadList(reqGrade){
  spClearTimer();
  var g=(typeof reqGrade==='number'&&reqGrade)?reqGrade:(SPGRADE||maInitGrade());
  root.textContent='';
  SPTOP=el('div');SPMSG=el('div',{class:'ma-notice',role:'status'});SPBOX=el('div',{class:'ma-wrap'});
  root.appendChild(el('div',{class:'ma-wrap'},SPTOP,SPMSG,SPBOX));
  var url='/student/math-sprints'+(g?('?grade='+encodeURIComponent(g)):'');
  Promise.all([api(url),maFetchTasks('数学')]).then(function(res){
    var d=res[0],tasks=res[1]||[];
    SPDATA=d;
    var curGrade=d.grade||g||5;
    SPGRADE=curGrade;window.__CY_ARENA_GRADE__=curGrade;
    SPTOP.textContent='';SPTOP.appendChild(maTopbar('sprints',d.points,curGrade));
    SPBOX.textContent='';
    SPBOX.appendChild(maRenderGradeBar(d,function(newGrade){
      SPGRADE=newGrade;
      spLoadList(newGrade);
    }));
    SPBOX.appendChild(el('div',{class:'ma-card'},
      el('div',{class:'ma-eyebrow',text:'小学数学 · '+curGrade+'年级强应试限时模块'}),
      el('h2',{class:'ma-h1',text:'应试专项'}),
      el('p',{class:'ma-sub',text:'多题型严格限时，倒计时归零自动交卷。按得分率与配速评定 L1（60%）/ L2 达标（75%）/ L3 熟练（85%）/ L4 冲刺（95%），达标自动反哺点亮知识地图。'})));
    var banner=maRenderTaskBanner(tasks,function(t){
      var tGrade=t.grade||maInferGrade(t.targetKey,curGrade);
      if(t.taskKind==='sprint'){
        if(Number(tGrade)!==Number(curGrade)){
          SPGRADE=Number(tGrade);window.__CY_ARENA_GRADE__=Number(tGrade);
        }
        spStart(t.targetKey);
      }else{
        location.href='/v1/math-star-map?grade='+encodeURIComponent(tGrade)+'#node='+encodeURIComponent(t.targetKey);
      }
    });
    if(banner)SPBOX.appendChild(banner);
    SPBOX.appendChild(maHelperTip('应试专项模拟真实考场，时间一到会自动交卷！建议先稳拿选择、判断和计算分，最后留时间攻克易错辨析与综合推理题。','长缨助手 · 考场配速建议'));
    var grid=el('div',{class:'ma-sprints'});
    d.items.forEach(function(sp){
      var hasSpTask=tasks.some(function(t){return t.taskKind==='sprint'&&t.targetKey===sp.slug});
      var tags=el('div',{class:'ma-sprint-tags'},
        hasSpTask?el('span',{class:'ma-task-badge',text:'老师任务'}):null,
        el('span',{class:'ma-pill',text:'限时 '+sp.timeLimitMin+' 分钟'}),
        el('span',{class:'ma-pill',text:sp.questionCount+' 题'}));
      sp.types.forEach(function(t){tags.appendChild(el('span',{class:'ma-pill',text:t.label+'×'+t.count}))});
      var tierLine=sp.bestTier?('最高：'+sp.bestTier.code+' '+sp.bestTier.name+'（'+sp.bestScoreRate+'%）'):'尚未挑战';
      grid.appendChild(el('div',{class:'ma-sprint'},
        el('div',{},
          el('h3',{text:sp.title}),
          el('p',{class:'ma-muted',text:sp.subtitle}),
          tags,
          el('p',{style:'margin:10px 0 0;font-size:13.5px;font-weight:700;color:var(--ma-brand)',text:tierLine})),
        el('button',{type:'button',class:'ma-btn ma-btn-primary',text:'开始限时挑战',onclick:function(){spStart(sp.slug)}})));
    });
    SPBOX.appendChild(grid);
    if(d.recent&&d.recent.length){
      var hist=el('div',{class:'ma-card'},el('h3',{text:'最近记录'}));
      d.recent.forEach(function(r){
        hist.appendChild(el('p',{class:'ma-muted',style:'margin-top:6px',text:r.submittedAt+' · '+r.title+' · '+r.tier.code+' '+r.tier.name+' · '+r.earnedMarks+'/'+r.totalMarks+' 分（'+r.scoreRate+'%）· 用时 '+maClockText(r.elapsedSec)}));
      });
      SPBOX.appendChild(hist);
    }
    var wantSp=/[#&]sprint=([^&]+)/.exec(location.hash);
    if(wantSp){
      var spSlug=decodeURIComponent(wantSp[1]);
      if(window.history&&window.history.replaceState){
        try{window.history.replaceState(null,'',location.pathname+location.search)}catch(_e){}
      }
      spStart(spSlug);
    }
  }).catch(function(e){msg(e.message)});
}
function spStart(slug){
  spSay('正在生成限时试卷…');
  api('/student/math-sprints/'+encodeURIComponent(slug)+'/start',{method:'POST'}).then(function(d){
    spSay('');
    if(d&&d.grade){SPGRADE=d.grade;window.__CY_ARENA_GRADE__=d.grade}
    spRunPaper(d);
  }).catch(function(e){spSay(e.message,true)});
}
function spRunPaper(d){
  spClearTimer();
  SPBOX.textContent='';
  var ageProf=d.ageProfile||(SPDATA&&SPDATA.ageProfile)||{};
  var spGrade=Number(d.grade||SPGRADE||5);
  var isG12=(ageProf.tier==='g12_playful'||spGrade===1||spGrade===2);
  var isG3=(ageProf.tier==='g3_guided'||spGrade===3);
  var ageCls=isG12?' ma-age-g12 ma-age-g3':(isG3?' ma-age-g3':'');
  var answers={},submitted=false,cur=0,allMode=false;
  var limitSec=d.timeLimitSec,endAt=Date.now()+limitSec*1000;
  var clockEl=el('span',{class:'ma-clock',text:'剩余 '+maClockText(limitSec)});
  var statEl=el('span',{class:'ma-muted',text:'已答 0/'+d.questionCount+' 题'});
  var barFill=el('div',{class:'ma-prog-fill',style:'width:100%'});
  var confirmHolder=el('div');
  var modeBtn=el('button',{type:'button',class:'ma-btn ma-btn-ghost ma-btn-sm',text:'整卷浏览',onclick:function(){
    allMode=!allMode;modeBtn.textContent=allMode?'单题专注':'整卷浏览';renderBody();
  }});
  var exitBtn=el('button',{type:'button',class:'ma-btn ma-btn-ghost ma-btn-sm',text:'退出',onclick:function(){
    showConfirm('正在计时中，确定退出本次专项吗？','确认退出',function(){spLoadList()});
  }});
  var submitBtn=el('button',{type:'button',class:'ma-btn ma-btn-primary ma-btn-sm',text:'交卷评级',onclick:function(){
    var doneCnt=Object.keys(answers).length;
    if(doneCnt<d.questionCount){
      showConfirm('还有 '+(d.questionCount-doneCnt)+' 题未答，未答题按 0 分计，确定交卷？','确认交卷',function(){doSubmit(false)});
    }else{doSubmit(false)}
  }});
  var hud=el('div',{class:'ma-hud',role:'timer'},
    el('div',{class:'ma-hud-top'},
      el('div',{},el('b',{text:d.title}),el('span',{class:'ma-muted',style:'margin-left:10px'},statEl)),
      el('div',{class:'ma-row'},clockEl,modeBtn,exitBtn,submitBtn)),
    el('div',{class:'ma-prog-track'},barFill));
  var sheet=el('div',{class:'ma-sheet'});
  var body=el('div',{class:'ma-wrap'+ageCls});
  SPBOX.appendChild(hud);SPBOX.appendChild(confirmHolder);SPBOX.appendChild(sheet);SPBOX.appendChild(body);

  function showConfirm(text,okLabel,onOk){
    confirmHolder.textContent='';
    confirmHolder.appendChild(el('div',{class:'ma-confirm'},
      el('span',{text:text}),
      el('div',{class:'ma-row'},
        el('button',{type:'button',class:'ma-btn ma-btn-primary ma-btn-sm',text:okLabel,onclick:function(){confirmHolder.textContent='';onOk()}}),
        el('button',{type:'button',class:'ma-btn ma-btn-ghost ma-btn-sm',text:'继续作答',onclick:function(){confirmHolder.textContent=''}}))));
  }
  function refreshSheet(){
    var doneCnt=Object.keys(answers).length;
    statEl.textContent='已答 '+doneCnt+'/'+d.questionCount+' 题';
    sheet.textContent='';
    sheet.appendChild(el('span',{class:'ma-muted',style:'font-weight:700',text:'答题卡：'}));
    d.questions.forEach(function(q,idx){
      var cls='ma-dot'+(!allMode&&idx===cur?' cur':(answers[q.id]?' done':''));
      var dot=el('button',{type:'button',class:cls,text:String(idx+1),onclick:function(){
        cur=idx;
        if(!allMode){renderBody()}else{
          var elQ=body.querySelector('[data-q="'+q.id+'"]');
          if(elQ&&elQ.scrollIntoView)elQ.scrollIntoView({behavior:'smooth',block:'center'});
        }
      }});
      if(q.hasFigure)dot.appendChild(el('span',{class:'ma-dot-fig'}));
      sheet.appendChild(dot);
    });
  }
  function buildQCard(q,idx){
    var card=el('div',{class:'ma-q-card','data-q':q.id},
      el('div',{class:'ma-q-meta'},el('span',{text:'第 '+(idx+1)+' / '+d.questionCount+' 题 · '+q.typeLabel+'（'+q.marks+' 分）'}),el('span',{text:'知识点 '+q.nodeKey})),
      maBuildStemRow(q,ageProf));
    if(typeof cyIsDrawnFigure==='function'&&cyIsDrawnFigure(q.figure)){
      card.appendChild(el('div',{class:'ma-fig-box'},cyCubeSvgNode(q.figure)));
    }
    if(q.questionType==='single_choice'||q.questionType==='true_false'){
      var opts=el('div',{class:'ma-opts'});
      (q.options||[]).forEach(function(o,k){
        var picked=answers[q.id]&&answers[q.id].selected_index===k;
        var b=el('button',{type:'button',class:'ma-opt'+(picked?' picked':''),onclick:function(){
          if(submitted)return;
          answers[q.id]={question_id:q.id,selected_index:k};
          Array.prototype.forEach.call(opts.children,function(c){c.className='ma-opt'});
          b.className='ma-opt picked';
          refreshSheet();
        }},el('span',{class:'ma-opt-k',text:String.fromCharCode(65+k)}),el('span',{text:o}));
        opts.appendChild(b);
      });
      card.appendChild(opts);
    }else{
      var prev=answers[q.id]&&answers[q.id].text_answer?answers[q.id].text_answer:'';
      var inp=el('input',{class:'ma-input','aria-label':'第'+(idx+1)+'题答案',placeholder:'输入答案',maxlength:'120',value:prev});
      function syncSpVal(rawVal){
        if(submitted)return;
        var v=String(rawVal||'').trim();
        if(v)answers[q.id]={question_id:q.id,text_answer:v};
        else delete answers[q.id];
        refreshSheet();
      }
      inp.addEventListener('input',function(){syncSpVal(inp.value)});
      card.appendChild(inp);
      var pad=maBuildMathKeypad(inp,ageProf,syncSpVal);
      if(pad)card.appendChild(pad);
    }
    return card;
  }
  function renderBody(){
    refreshSheet();
    body.textContent='';
    if(allMode){
      d.questions.forEach(function(q,i){body.appendChild(buildQCard(q,i))});
    }else{
      var q=d.questions[cur],card=buildQCard(q,cur);
      var l=el('div',{class:'ma-row'}),r=el('div',{class:'ma-row'});
      if(cur>0)l.appendChild(el('button',{type:'button',class:'ma-btn ma-btn-ghost ma-btn-sm',text:'上一题',onclick:function(){cur--;renderBody()}}));
      if(cur<d.questions.length-1)r.appendChild(el('button',{type:'button',class:'ma-btn ma-btn-primary ma-btn-sm',text:'下一题',onclick:function(){cur++;renderBody()}}));
      card.appendChild(el('div',{class:'ma-foot'},l,r));
      body.appendChild(card);
    }
  }
  function doSubmit(isAuto){
    if(submitted)return;
    if(window.speechSynthesis){try{window.speechSynthesis.cancel()}catch(_e){}}
    submitted=true;spClearTimer();submitBtn.disabled=true;
    spSay(isAuto?'时间到，正在自动交卷…':'正在判分…');
    var list=[];Object.keys(answers).forEach(function(k){list.push(answers[k])});
    api('/student/math-sprints/attempts/'+d.attemptId+'/submit',{json:{answers:list,auto_submitted:!!isAuto}}).then(function(r){
      spSay('');spShowResult(d,r);
    }).catch(function(e){submitted=false;submitBtn.disabled=false;spSay(e.message,true)});
  }
  function tick(){
    var left=Math.ceil((endAt-Date.now())/1000);
    if(left<=0){
      clockEl.textContent='时间到 · 自动交卷';barFill.style.width='0%';hud.className='ma-hud urgent';
      doSubmit(true);return;
    }
    clockEl.textContent='剩余 '+maClockText(left);
    barFill.style.width=Math.max(0,Math.min(100,Math.round(left/limitSec*100)))+'%';
    hud.className=left<=60?'ma-hud urgent':'ma-hud';
  }
  renderBody();tick();
  SPTIMER=setInterval(tick,500);
  window.scrollTo(0,0);
}
function spShowResult(d,r){
  var curGrade=r.grade||d.grade||SPGRADE||5;
  if(r.points){SPTOP.textContent='';SPTOP.appendChild(maTopbar('sprints',r.points,curGrade))}
  SPBOX.textContent='';
  SPBOX.appendChild(el('div',{class:'ma-card ma-res-head'},
    el('div',{class:'ma-res-tier',text:r.tier.code+' · '+r.tier.name}),
    el('h2',{text:'得分 '+r.earnedMarks+' / '+r.totalMarks+' 分（'+r.scoreRate+'%）'}),
    el('p',{class:'ma-muted',text:'答对 '+r.correctCount+'/'+r.questionCount+' 题 · 用时 '+maClockText(r.elapsedSec)+(r.autoSubmitted?'（到点自动交卷）':'')}),
    maPointsGain(r.pointsAwarded,r.points)));
  var resTip=r.tier.code==='L4'
    ?'满分冲刺太稳了！不仅拿下了钻章，对应考点也已同步升星，试试挑战其他专项吧！'
    :(r.topLosses.length
      ?'本次主要丢分在「'+r.topLosses[0].name+'」等 '+r.topLosses.length+' 个考点，点下方「去地图修补」做 5 题就能彻底拿下！'
      :'整体发挥很稳！保持这个配速，再刷一次冲击 L4 冲刺钻章吧！');
  SPBOX.appendChild(maHelperTip(resTip,'长缨助手 · 考后复盘'));
  if(r.mapChanges&&r.mapChanges.litNodes&&r.mapChanges.litNodes.length){
    var lit=el('div',{class:'ma-card'},el('h3',{text:'已自动反哺点亮知识地图'}));
    r.mapChanges.litNodes.forEach(function(n){lit.appendChild(el('div',{class:'ma-rev ok',text:n.key+' '+n.name+' → '+n.state}))});
    SPBOX.appendChild(lit);
  }
  var lossCard=el('div',{class:'ma-card'},el('h3',{text:r.topLosses.length?'失分点（已在地图标红待修补）':'零失分通关'}));
  if(r.topLosses.length){
    r.topLosses.forEach(function(x){
      var nGrade=maInferGrade(x.key,curGrade);
      lossCard.appendChild(el('div',{class:'ma-loss-row'},
        el('span',{text:x.key+' '+x.name+'（失 '+x.lostMarks+'/'+x.marks+' 分）'}),
        el('a',{class:'ma-btn ma-btn-primary ma-btn-sm',href:'/v1/math-star-map?grade='+encodeURIComponent(nGrade)+'#node='+encodeURIComponent(x.key),text:'去地图修补'})));
    });
  }else{
    lossCard.appendChild(el('p',{class:'ma-muted',text:'本次专项全部答对，对应节点星星已同步提升。'}));
  }
  SPBOX.appendChild(lossCard);
  var det=el('div',{class:'ma-card'},el('h3',{text:'逐题解析'}));
  r.details.forEach(function(it,idx){
    det.appendChild(el('div',{class:'ma-rev '+(it.correct?'ok':'bad'),text:(idx+1)+'. ['+it.typeLabel+'] '+(it.correct?'正确':(it.answered?'错误':'未作答')+'（答案：'+it.answer+'）')+' — '+it.explanation}));
  });
  SPBOX.appendChild(det);
  SPBOX.appendChild(el('div',{class:'ma-row'},
    el('button',{type:'button',class:'ma-btn ma-btn-primary',text:'再战一次',onclick:function(){spStart(d.slug)}}),
    el('button',{type:'button',class:'ma-btn ma-btn-ghost',text:'返回专项列表',onclick:function(){spLoadList(curGrade)}}),
    el('a',{class:'ma-btn ma-btn-ghost',href:'/v1/math-star-map'+maGradeQuery(curGrade),text:'查看知识地图'})));
  window.scrollTo(0,0);
}
maBoot(spLoadList);
"""


HELPER_AVATAR_JS = 'window.__CY_HELPER_AVATAR__="data:image/png;base64,' + AVATAR_PNG_B64 + '";\n'


def math_star_map_page_html() -> str:
    return _page("数学知识地图", HELPER_AVATAR_JS + ARENA_ROLE_HUB_JS + CUBES_JS + STAR_MAP_JS, True).replace("</head>", ARENA_CSS + "</head>", 1)


def math_sprints_page_html() -> str:
    return _page("数学应试专项", HELPER_AVATAR_JS + ARENA_ROLE_HUB_JS + CUBES_JS + SPRINTS_JS, True).replace("</head>", ARENA_CSS + "</head>", 1)


__all__ = ["STAR_MAP_JS", "SPRINTS_JS", "math_star_map_page_html", "math_sprints_page_html"]
