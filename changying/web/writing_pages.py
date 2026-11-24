"""Teacher writing review, unified projection preview, and frozen classroom."""


def writing_page():
    from changying.web.weekend_pages import _page
    html = _page('作文课', r'''
var query = new URLSearchParams(location.search);
var lid = query.get('lesson');
var sid = query.get('session');
var viewMode = query.get('view');
var data = null;
var noteBox = null;
var activeStage = 2;
var summaryBox = null;
var saving = false;

var roles = {
  pending: '待确认',
  review: '点名与回顾',
  model: '范文段落',
  model_image: '范文配图',
  picture: '看图写话图片',
  method: '写作方法与例句',
  task: '写作主题',
  feedback: '课后反馈要求'
};
var roleStage = {
  review: 1,
  model: 2,
  model_image: 2,
  picture: 3,
  method: 4,
  task: 5,
  feedback: 6
};
var verdictLabels = {
  passed: '通过',
  needs_revision: '需修改',
  retake: '需重拍'
};
var methodOptionRe = /^[A-F][\.、\s]?[\u4e00-\u9fff]/;

function message(e) {
  if (!noteBox) return;
  noteBox.textContent = (e && e.message) ? e.message : String(e || '');
  if (noteBox.scrollIntoView) noteBox.scrollIntoView({block: 'nearest'});
}

function button(label, fn, cls) {
  var attrs = {
    text: label,
    onclick: function() {
      Promise.resolve().then(fn).catch(message);
    }
  };
  if (cls) attrs.class = cls;
  return el('button', attrs);
}

function looksLikeMethodOption(text) {
  var t = String(text || '').trim();
  if (!t) return false;
  if (methodOptionRe.test(t)) return true;
  var matches = t.match(/[A-F][\.、\s]?[\u4e00-\u9fff]{2,}/g);
  return !!(matches && matches.length >= 2);
}

function activeNodesOf(nodes) {
  return (nodes || []).filter(function(n) { return n.status !== 'ignored'; });
}

function pairModelNodes(items) {
  var paragraphs = items.filter(function(n) { return n.role === 'model'; });
  var images = items.filter(function(n) { return n.role === 'model_image'; });
  var usedImageIds = {};
  var groups = [];
  paragraphs.forEach(function(p) {
    var bound = images.filter(function(img) {
      return (img.targets || []).indexOf(p.id) >= 0;
    });
    bound.forEach(function(img) { usedImageIds[img.id] = true; });
    groups.push({paragraph: p, images: bound});
  });
  var unbound = images.filter(function(img) { return !usedImageIds[img.id]; });
  return {groups: groups, unbound: unbound};
}

function renderStageContent(stageNo, allNodes, opts) {
  opts = opts || {};
  var box = el('div', {class: 'wr-stage-content'});
  var visible = activeNodesOf(allNodes);
  var items = visible.filter(function(n) { return Number(roleStage[n.role]) === Number(stageNo); });

  function attachControl(card, n) {
    if (!opts.renderControl) return;
    var ctrl = opts.renderControl(n);
    if (ctrl) card.appendChild(ctrl);
  }

  if (!items.length) {
    box.appendChild(el('p', {class: 'wr-empty', text: opts.emptyText || '本环节还没有内容。'}));
    return box;
  }

  if (Number(stageNo) === 2) {
    var paired = pairModelNodes(items);
    paired.groups.forEach(function(g, idx) {
      var p = g.paragraph;
      var hasImg = g.images.length > 0;
      var card = el('article', {class: 'wr-model-pair' + (hasImg ? ' has-media' : '')});
      var textCol = el('div', {class: 'wr-model-text'});
      attachControl(textCol, p);
      if (opts.onMoveToMethod && looksLikeMethodOption(p.text)) {
        var warn = el('div', {class: 'wr-inline-warn'});
        warn.appendChild(el('span', {text: '提示：该条疑似写作方法选项，误归入了范文正文。'}));
        warn.appendChild(button('一键移至技法梳理', function() { return opts.onMoveToMethod(p); }));
        textCol.appendChild(warn);
      }
      var isTitle = idx === 0 && (p.text || '').trim().length <= 18 && !/[。！？，]/.test(p.text || '');
      textCol.appendChild(el(isTitle ? 'h3' : 'p', {
        class: isTitle ? 'wr-model-title' : 'wr-model-para',
        text: p.text || ''
      }));
      card.appendChild(textCol);
      if (hasImg) {
        var mediaCol = el('div', {class: 'wr-model-media'});
        g.images.forEach(function(img) {
          var fig = el('figure', {class: 'wr-figure'});
          attachControl(fig, img);
          if (img.dataUrl) fig.appendChild(el('img', {src: img.dataUrl, alt: '范文配图'}));
          mediaCol.appendChild(fig);
        });
        card.appendChild(mediaCol);
      }
      box.appendChild(card);
    });
    if (paired.unbound.length) {
      var unbox = el('section', {class: 'wr-unbound-box'});
      if (opts.isEditor) {
        unbox.appendChild(el('p', {class: 'wr-inline-warn', text: '以下配图尚未绑定范文段落，请在下方“逐项修改文字、用途或配图绑定”中选择对应段落：'}));
      }
      var grid = el('div', {class: 'wr-gallery'});
      paired.unbound.forEach(function(img) {
        var fig = el('figure', {class: 'wr-figure'});
        attachControl(fig, img);
        if (img.dataUrl) fig.appendChild(el('img', {src: img.dataUrl, alt: '范文配图'}));
        grid.appendChild(fig);
      });
      unbox.appendChild(grid);
      box.appendChild(unbox);
    }
    return box;
  }

  if (Number(stageNo) === 3) {
    var gallery = el('div', {class: 'wr-gallery'});
    items.forEach(function(n, idx) {
      var fig = el('figure', {class: 'wr-figure wr-picture-card'});
      attachControl(fig, n);
      fig.appendChild(el('figcaption', {text: '图 ' + (idx + 1) + ' / ' + items.length}));
      if (n.dataUrl) fig.appendChild(el('img', {src: n.dataUrl, alt: '看图写话配图 ' + (idx + 1)}));
      if (n.text) fig.appendChild(el('p', {class: 'wr-caption-text', text: n.text}));
      gallery.appendChild(fig);
    });
    box.appendChild(gallery);
    return box;
  }

  if (Number(stageNo) === 4) {
    var bridge = el('section', {class: 'wr-bridge'});
    bridge.appendChild(el('h3', {text: '技法梳理：从范文到自己的描写'}));
    bridge.appendChild(el('p', {class: 'wr-bridge-lead', text: '结合范文中的具体写法与看图观察要点，梳理本次作文的核心表达方法，并迁移到自己的写作主题中。'}));

    var byId = {};
    visible.forEach(function(n) { byId[n.id] = n; });
    var methodList = el('ol', {class: 'wr-method-list'});
    items.forEach(function(n) {
      var li = el('li', {class: 'wr-method-card'});
      attachControl(li, n);
      if (n.text) li.appendChild(el('p', {class: 'wr-method-text', text: n.text}));
      if (n.dataUrl) li.appendChild(el('img', {src: n.dataUrl, alt: '技法配图', class: 'wr-method-img'}));
      var linked = (n.targets || []).map(function(tid) { return byId[tid]; }).filter(Boolean);
      if (linked.length) {
        var ref = el('div', {class: 'wr-method-ref'});
        linked.forEach(function(refNode) {
          if (refNode.text) ref.appendChild(el('p', {class: 'wr-ref-quote', text: '对应范文：' + refNode.text}));
          if (refNode.dataUrl) ref.appendChild(el('img', {src: refNode.dataUrl, alt: '关联配图', class: 'wr-ref-img'}));
        });
        li.appendChild(ref);
      }
      methodList.appendChild(li);
    });
    bridge.appendChild(methodList);

    var examples = visible.filter(function(n) { return n.role === 'model' && (n.text || '').trim(); });
    var substantive = examples.filter(function(n) { return (n.text || '').trim().length >= 20 && !looksLikeMethodOption(n.text); });
    var refExample = substantive.length ? substantive[0] : (examples.length ? examples[0] : null);
    var pictures = visible.filter(function(n) { return n.role === 'picture' && n.dataUrl; });
    var taskNode = visible.filter(function(n) { return n.role === 'task' && (n.text || '').trim(); })[0] || null;

    if (refExample || pictures.length) {
      var refGrid = el('div', {class: 'wr-bridge-refs'});
      if (refExample) {
        var exCard = el('div', {class: 'wr-bridge-ref-card'});
        exCard.appendChild(el('h4', {text: '回看范文片段'}));
        exCard.appendChild(el('p', {class: 'wr-model-para', text: refExample.text}));
        refGrid.appendChild(exCard);
      }
      if (pictures.length) {
        var picCard = el('div', {class: 'wr-bridge-ref-card'});
        picCard.appendChild(el('h4', {text: '回看看图写话（共 ' + pictures.length + ' 图）'}));
        var thumbs = el('div', {class: 'wr-mini-gallery'});
        pictures.forEach(function(pic, idx) {
          thumbs.appendChild(el('img', {src: pic.dataUrl, alt: '看图写话参考图 ' + (idx + 1)}));
        });
        picCard.appendChild(thumbs);
        refGrid.appendChild(picCard);
      }
      bridge.appendChild(refGrid);
    }

    var transfer = el('div', {class: 'wr-transfer-box'});
    transfer.appendChild(el('h4', {text: '迁移到自己的作文'}));
    transfer.appendChild(el('p', {
      text: taskNode
        ? ('围绕《' + taskNode.text.trim() + '》，任选 1–2 个方法，先口头说两句有顺序、有细节的描写，再落笔修改其中一句。')
        : '围绕本次写作主题，任选 1–2 个方法，先说两句有顺序、有细节的描写，再落笔修改其中一句。'
    }));
    bridge.appendChild(transfer);
    box.appendChild(bridge);
    return box;
  }

  items.forEach(function(n) {
    var card = el('section', {class: 'wr-stage-card'});
    attachControl(card, n);
    if (n.text) card.appendChild(el('p', {class: 'wr-model-para', text: n.text}));
    if (n.dataUrl) card.appendChild(el('img', {src: n.dataUrl, alt: roles[n.role] || '配图', class: 'wr-stage-img'}));
    box.appendChild(card);
  });
  return box;
}

function showCoverage() {
  if (!summaryBox || !data || !data.package) return;
  var rows = (data.readiness && data.readiness.stageReadiness) || [];
  var missing = [];
  rows.forEach(function(stage) {
    if (stage.missing && stage.missing.length) {
      missing.push(stage.name + '缺' + stage.missing.join('、'));
    }
  });
  var pending = (data.readiness && data.readiness.pendingMaterials) || 0;
  var head = '六环节素材核对：';
  if (!missing.length && !pending && data.readiness && data.readiness.canStart) {
    summaryBox.textContent = head + '六环节均已就绪并通过审核，可直接投屏预览或创建课堂。';
  } else {
    var parts = [];
    if (missing.length) parts.push(missing.join('；'));
    if (pending) parts.push(pending + ' 项素材待确认或忽略');
    if (!parts.length) parts.push('各环节素材齐备，点击“审核通过”后即可开课');
    summaryBox.textContent = head + parts.join('；') + '。';
  }
}

function prepare() {
  return api('/teacher/weekend/lessons/' + lid + '/writing').then(function(d) {
    data = d;
    if (viewMode === 'preview') {
      activeStage = 1;
      paintPreview();
      return;
    }
    var remembered = sessionStorage.getItem('writing-stage-' + lid);
    var first = (d.package && d.package.nodes || []).filter(function(n) {
      return n.status === 'pending' && roleStage[n.role];
    }).map(function(n) { return roleStage[n.role]; }).sort()[0];
    activeStage = remembered === 'pending' ? 'pending' : (Number(remembered) >= 1 && Number(remembered) <= 6 ? Number(remembered) : first || 1);
    paintEditor();
    if (query.get('imported') === '1') {
      message('已导入备课草稿');
      query.delete('imported');
      history.replaceState(null, '', location.pathname + '?' + query.toString());
    }
  });
}

function selectStage(stage) {
  activeStage = stage;
  sessionStorage.setItem('writing-stage-' + lid, String(stage));
  paintEditor();
  var panel = root.querySelector('.wr-stage-panel');
  if (panel) {
    panel.focus();
    panel.scrollIntoView({block: 'start'});
  }
}

function paintPreview() {
  root.className = 'writing-review writing-preview';
  root.textContent = '';
  noteBox = el('p', {role: 'status'});
  if (!data || !data.package) {
    root.appendChild(el('h1', {text: '课堂投屏预览'}));
    root.appendChild(noteBox);
    message('当前课程还没有作文素材包。');
    return;
  }
  var bar = el('div', {class: 'wr-preview-bar'});
  bar.appendChild(el('h1', {text: (data.package.title || '作文课') + ' · 课堂投屏预览'}));
  var nav = el('div', {class: 'wr-preview-nav'});
  var readiness = (data.readiness && data.readiness.stageReadiness) || [];
  readiness.forEach(function(s, idx) {
    var st = idx + 1;
    var b = button(st + '. ' + s.name, function() { activeStage = st; paintPreview(); }, Number(activeStage) === st ? 'primary' : '');
    nav.appendChild(b);
  });
  bar.appendChild(nav);
  root.appendChild(bar);
  root.appendChild(noteBox);

  var stageInfo = readiness[Number(activeStage) - 1] || {name: '第 ' + activeStage + ' 环节'};
  var board = el('section', {class: 'wr-preview-stage'});
  board.appendChild(el('h2', {text: activeStage + '. ' + stageInfo.name}));
  board.appendChild(renderStageContent(activeStage, data.package.nodes, {
    emptyText: '本环节暂无可展示的素材，请返回备课审核页补充。'
  }));
  root.appendChild(board);

  var pager = el('div', {class: 'wr-preview-pager'});
  if (Number(activeStage) > 1) {
    pager.appendChild(button('上一环节', function() { activeStage = Number(activeStage) - 1; paintPreview(); }));
  }
  if (Number(activeStage) < 6) {
    pager.appendChild(button('下一环节', function() { activeStage = Number(activeStage) + 1; paintPreview(); }, 'primary'));
  }
  pager.appendChild(el('a', {href: '/v1/weekend-writing?lesson=' + encodeURIComponent(lid), class: 'btn', text: '返回素材审核页'}));
  root.appendChild(pager);
}

function paintEditor() {
  root.className = 'writing-review';
  root.textContent = '';
  noteBox = el('p', {role: 'status'});
  root.appendChild(el('h1', {text: '作文素材与审核'}));
  root.appendChild(noteBox);

  var back = '/v1/weekend-plan?subject=' + encodeURIComponent('语文') + '&lesson=' + encodeURIComponent(lid);
  var topLinks = el('div', {class: 'wr-top-links'});
  topLinks.appendChild(el('a', {href: back, text: '返回本课课次行'}));
  if (data.package) {
    topLinks.appendChild(el('a', {
      href: '/v1/weekend-writing?lesson=' + encodeURIComponent(lid) + '&view=preview',
      target: '_blank',
      rel: 'noopener',
      class: 'btn',
      text: '课堂投屏预览（新窗口）'
    }));
    topLinks.appendChild(el('a', {
      href: back + '&view=courseware',
      text: '查看兼容课件页'
    }));
  }
  root.appendChild(topLinks);

  if (data.package) {
    summaryBox = el('p', {role: 'note', class: 'wr-coverage-note'});
    root.appendChild(summaryBox);
    showCoverage();
  }
  if (!data.package) {
    message('请从备课工作栏导入作文教案。');
    return;
  }

  var titleRow = el('div', {class: 'wr-title-row'});
  titleRow.appendChild(el('label', {text: '课题名称'}));
  var title = el('input', {'aria-label': '课程标题', value: data.package.title || ''});
  title.oninput = function() { data.package.title = title.value; };
  titleRow.appendChild(title);
  root.appendChild(titleRow);

  root.appendChild(el('p', {class: 'wr-intro', text: '按作文六环节整理材料。先选环节，再核对该环节的图文排版与来源；改动后需重新审核，已创建课堂仍使用原冻结版本。'}));

  var counts = {pending: 0, confirmed: 0, ignored: 0};
  data.package.nodes.forEach(function(n) { counts[n.status] = (counts[n.status] || 0) + 1; });
  var summary = el('div', {class: 'wr-summary', 'aria-label': '素材审核概况'});
  [['待确认', counts.pending], ['已确认', counts.confirmed], ['已忽略', counts.ignored]].forEach(function(x) {
    summary.appendChild(el('div', {class: 'wr-stat'}, el('strong', {text: String(x[1])}), x[0] + '项素材'));
  });
  root.appendChild(summary);

  var actions = el('div', {class: 'wr-review-actions'});
  actions.appendChild(button('保存草稿', function() { return save(false); }));
  actions.appendChild(button('审核通过', function() { return save(true); }, 'primary'));
  actions.appendChild(noteBox);
  root.appendChild(actions);

  var assigned = data.package.nodes.filter(function(n) { return n.status === 'pending' && n.role && n.role !== 'pending'; }).length;
  var pendingUnassigned = data.package.nodes.filter(function(n) { return !roleStage[n.role] && n.status === 'pending'; }).length;

  var tools = el('details', {class: 'wr-tools'});
  tools.appendChild(el('summary', {text: '补充或批量处理素材'}));
  tools.appendChild(el('p', {text: '批量操作会记入修订历史；确认素材归属不等于整课审核通过。'}));
  var toolrow = el('div', {class: 'row'});
  toolrow.appendChild(button('确认已分类（' + assigned + '项）', function() {
    if (!assigned) throw Error('没有待确认的已分类素材');
    if (!confirm('确认你已检查并同意这 ' + assigned + ' 项素材的归属及内容吗？审核通过仍需另行操作。')) return;
    return api('/teacher/weekend/lessons/' + lid + '/writing/bulk-review', {
      method: 'POST',
      json: {expectedRevision: data.revision, action: 'confirm_assigned'}
    }).then(function(d) {
      data = d;
      paintEditor();
      message('已确认 ' + d.updated + ' 项；课程仍未审核通过');
    });
  }));
  toolrow.appendChild(button('忽略待分类（' + pendingUnassigned + '项）', function() {
    if (!pendingUnassigned) throw Error('没有待处理的未分类素材');
    if (!confirm('确认这 ' + pendingUnassigned + ' 项不纳入本次作文课？素材会保留在原始记录和修订历史中。')) return;
    return api('/teacher/weekend/lessons/' + lid + '/writing/bulk-review', {
      method: 'POST',
      json: {expectedRevision: data.revision, action: 'ignore_unassigned'}
    }).then(function(d) {
      data = d;
      paintEditor();
      message('已将 ' + d.updated + ' 项标为忽略；可以在素材列表中恢复审核');
    });
  }));
  toolrow.appendChild(button('导入已确认配图', function() {
    return api('/teacher/weekend/lessons/' + lid + '/writing/imported-images', {method: 'POST', json: {}}).then(function(d) {
      data = d;
      paintEditor();
      message(d.created ? '已将 ' + d.created + ' 张图片加入作文包；请逐张确认并绑定范文段落' : '没有新的已确认配图可导入');
    });
  }));
  toolrow.appendChild(button('新增文字素材', function() {
    var defaultRole = activeStage === 'pending' ? 'pending'
      : activeStage === 1 ? 'review'
      : activeStage === 2 ? 'model'
      : activeStage === 3 ? 'picture'
      : activeStage === 4 ? 'method'
      : activeStage === 5 ? 'task'
      : 'feedback';
    data.package.nodes.push({
      id: 'manual-' + Date.now(),
      kind: 'text',
      text: '',
      role: defaultRole,
      status: 'pending',
      targets: []
    });
    paintEditor();
  }));
  var file = el('input', {type: 'file', accept: 'image/*', 'aria-label': '补充图片'});
  toolrow.appendChild(file);
  toolrow.appendChild(button('上传图片', function() {
    if (!file.files[0]) throw Error('请先选择图片');
    return save(false).then(function() {
      var fd = new FormData();
      fd.append('file', file.files[0]);
      fd.append('expectedRevision', data.revision);
      return api('/teacher/weekend/lessons/' + lid + '/writing/images', {method: 'POST', body: fd});
    }).then(function(d) {
      data = d;
      paintEditor();
      message('图片已上传，请在“待分类”中分配用途并绑定段落。');
    });
  }));
  tools.appendChild(toolrow);
  root.appendChild(tools);

  var readiness = data.readiness.stageReadiness || [];
  var nav = el('nav', {class: 'wr-stages', 'aria-label': '作文六环节'});
  readiness.forEach(function(s, index) {
    var stage = index + 1;
    var items = data.package.nodes.filter(function(n) { return Number(roleStage[n.role]) === stage; });
    var pending = items.filter(function(n) { return n.status === 'pending'; }).length;
    var b = button(stage + '. ' + s.name, function() { selectStage(stage); });
    b.className = 'wr-stage';
    b.setAttribute('aria-pressed', String(Number(activeStage) === stage));
    b.appendChild(el('small', {
      text: (pending ? '待审核' : s.status) +
        (pending ? ' · ' + pending + '项待确认' : '') +
        (s.missing && s.missing.length ? ' · ' + s.missing.join('、') : '')
    }));
    nav.appendChild(b);
  });
  var ub = button('待分类', function() { selectStage('pending'); });
  ub.className = 'wr-stage';
  ub.setAttribute('aria-pressed', String(activeStage === 'pending'));
  ub.appendChild(el('small', {text: pendingUnassigned + '项待分类素材'}));
  nav.appendChild(ub);
  root.appendChild(nav);

  var section = el('section', {class: 'wr-stage-panel', tabindex: '-1'},
    el('h2', {text: activeStage === 'pending' ? '待分类素材' : (readiness[Number(activeStage) - 1] || {}).name || ''})
  );
  var stageNodes = data.package.nodes.map(function(n, i) { return {node: n, index: i}; }).filter(function(x) {
    return activeStage === 'pending' ? !roleStage[x.node.role] : Number(roleStage[x.node.role]) === Number(activeStage);
  });
  if (!stageNodes.length) {
    section.appendChild(el('p', {text: '本环节还没有素材。可从“补充或批量处理素材”添加文字或图片。'}));
  }
  var pendingHere = stageNodes.filter(function(entry) { return entry.node.status === 'pending'; });
  var materialList = section;

  if (activeStage !== 'pending' && stageNodes.length) {
    section.appendChild(renderStageContent(activeStage, data.package.nodes, {
      isEditor: true,
      emptyText: '本环节有效素材为空（其余已忽略）。',
      onMoveToMethod: function(node) {
        node.role = 'method';
        node.status = 'pending';
        return save(false).then(function() {
          message('已将该条移至“4. 技法梳理”，请前往核对。');
        });
      }
    }));
    if (pendingHere.length) {
      section.appendChild(button('确认本环节素材（' + pendingHere.length + '项）', function() {
        return save(false, pendingHere.map(function(entry) { return entry.node.id; }));
      }, 'primary'));
    }
    materialList = el('details', {class: 'wr-edit-drawer'});
    materialList.appendChild(el('summary', {text: '逐项修改文字、用途或配图绑定'}));
    section.appendChild(materialList);
  }

  stageNodes.forEach(function(entry) {
    var n = entry.node;
    var i = entry.index;
    var card = el('section', {class: 'wr-item'});
    var head = el('div', {class: 'wr-item-head'});
    var role = el('select', {'aria-label': '素材归属'});
    var status = el('select', {'aria-label': '审核状态'});
    var text = el('textarea', {'aria-label': '素材正文'});
    Object.keys(roles).forEach(function(k) {
      role.appendChild(el('option', {value: k, text: roles[k], selected: n.role === k}));
    });
    role.onchange = function() { n.role = role.value; };
    ['pending', 'confirmed', 'ignored'].forEach(function(k) {
      status.appendChild(el('option', {value: k, text: {pending: '待确认', confirmed: '确认', ignored: '忽略'}[k], selected: n.status === k}));
    });
    status.onchange = function() { n.status = status.value; };
    text.value = n.text || '';
    text.oninput = function() { n.text = text.value; };
    head.appendChild(el('strong', {text: (i + 1) + ' · ' + (n.kind === 'image' ? '图片素材' : '文字素材')}));
    head.appendChild(el('span', {
      class: 'tag ' + (n.status === 'confirmed' ? 'ok' : 'warn'),
      text: {pending: '待确认', confirmed: '已确认', ignored: '已忽略'}[n.status] || '待确认'
    }));
    card.appendChild(head);
    if (n.dataUrl) card.appendChild(el('img', {src: n.dataUrl, alt: '素材原图'}));
    if (n.text || n.kind !== 'image') card.appendChild(text);
    var fields = el('div', {class: 'wr-bindings'});
    fields.appendChild(el('label', {}, '用途 ', role));
    fields.appendChild(el('label', {}, '状态 ', status));
    card.appendChild(fields);

    var source = el('details');
    source.appendChild(el('summary', {text: '查看原件来源与识别依据'}));
    source.appendChild(el('p', {
      class: 'wr-source',
      text: '来源：' + JSON.stringify(n.source || {}) +
        (n.declaredSource ? '；素材声明：' + JSON.stringify(n.declaredSource) : '') +
        '；识别依据：' + (n.reason || '教师配置')
    }));
    card.appendChild(source);

    if (n.kind === 'image') {
      card.appendChild(el('p', {text: '这张图对应哪段范文？（可多选）'}));
      var bindings = el('div', {class: 'wr-bindings'});
      data.package.nodes.filter(function(p) { return p.role === 'model' && p.status !== 'ignored'; }).forEach(function(p) {
        var check = el('input', {type: 'checkbox', checked: (n.targets || []).indexOf(p.id) >= 0});
        check.onchange = function() {
          n.targets = (n.targets || []).filter(function(x) { return x !== p.id; });
          if (check.checked) n.targets.push(p.id);
        };
        bindings.appendChild(el('label', {}, check, (p.text || '未填写段落').slice(0, 100)));
      });
      card.appendChild(bindings);
    }

    var edit = el('details');
    edit.appendChild(el('summary', {text: '整理文字与顺序'}));
    edit.appendChild(button('上移', function() {
      if (i) {
        data.package.nodes.splice(i, 1);
        data.package.nodes.splice(i - 1, 0, n);
        paintEditor();
      }
    }));
    edit.appendChild(button('按换行拆分', function() {
      var pieces = (n.text || '').split(/\n+/).filter(Boolean);
      if (pieces.length < 2) throw Error('请先用换行分段');
      n.status = 'ignored';
      pieces.forEach(function(t, j) {
        data.package.nodes.splice(i + 1 + j, 0, {
          id: 'split-' + Date.now() + '-' + j,
          derivedFrom: n.id,
          kind: 'text',
          text: t,
          role: n.role,
          status: 'pending',
          targets: []
        });
      });
      paintEditor();
    }));
    edit.appendChild(button('与下一段合并', function() {
      var next = data.package.nodes[i + 1];
      if (!next || next.kind === 'image') throw Error('下一项不能合并');
      n.text += '\n' + next.text;
      next.status = 'ignored';
      n.status = 'pending';
      paintEditor();
    }));
    card.appendChild(edit);
    materialList.appendChild(card);
  });
  root.appendChild(section);

  root.appendChild(el('p', {class: 'wr-intro', text: '图片是否适合作文场景、段落是否完整，需要老师核对原件。图片截图和思维导图不会自动当作配图。'}));

  if (data.readiness.startReasons && data.readiness.startReasons.length) {
    var todoDetails = el('details', {});
    todoDetails.appendChild(el('summary', {text: '查看开课前待办（' + data.readiness.startReasons.length + '）'}));
    var ul = el('ul', {});
    data.readiness.startReasons.forEach(function(reason) {
      ul.appendChild(el('li', {text: reason}));
    });
    todoDetails.appendChild(ul);
    root.appendChild(todoDetails);
  } else {
    root.appendChild(el('p', {class: 'notice ok', text: '六环节素材已满足开课检查。'}));
  }

  if (data.readiness.canStart) {
    root.appendChild(button('选择班级并保存待开课堂', function() {
      if (!data.readiness.canStart) throw Error('请先完成审核');
      chooseWeekendClass(function(classId) {
        return api('/teacher/weekend/sessions', {json: {lessonId: Number(lid), classId: classId}}).then(function(s) {
          location.href = '/v1/weekend-writing?session=' + s.id;
        });
      });
    }, 'primary'));
  }

  root.appendChild(el('p', {
    class: 'wr-intro',
    text: '预约日期在备课工作栏填写；保存待开课堂后，教师可在课堂页点击“立即开始”。修订 ' +
      data.revision + ' · 历史修改 ' + (data.package.history || []).length + ' 次。'
  }));
}

function save(approve, confirmIds) {
  if (saving) return;
  var nodes = data.package.nodes.map(function(n) {
    return {
      id: n.id,
      derivedFrom: n.derivedFrom,
      text: n.text,
      role: n.role,
      status: (confirmIds && confirmIds.indexOf(n.id) >= 0) ? 'confirmed' : n.status,
      targets: n.targets || []
    };
  });
  var pending = nodes.filter(function(n) { return n.status === 'pending'; });
  if (approve && pending.length) {
    message('整课尚未通过：还有 ' + pending.length + ' 项待处理。核对各环节后点“确认本环节素材”；待分类内容可归类或忽略。');
    return;
  }
  saving = true;
  message(approve ? '正在审核整课…' : '正在保存…');
  return api('/teacher/weekend/lessons/' + lid + '/writing', {
    method: 'PUT',
    json: {expectedRevision: data.revision, nodes: nodes, title: data.package.title || '', approve: approve}
  }).then(function(d) {
    data = d;
    paintEditor();
    var left = d.package.nodes.filter(function(n) { return n.status === 'pending'; }).length;
    message(approve
      ? '整课审核通过，可以选择班级开课'
      : confirmIds
        ? ('本环节已确认 ' + confirmIds.length + ' 项，全课剩余 ' + left + ' 项待处理。')
        : ('草稿已保存，仍有 ' + left + ' 项素材待确认。'));
  }).catch(function(e) {
    throw Error((approve ? '整课未通过：' : '保存失败：') + e.message);
  }).finally(function() {
    saving = false;
  });
}

function loadClass() {
  return api('/weekend/writing/sessions/' + sid).then(function(d) {
    data = d;
    paintClass();
  });
}

function paintClass() {
  root.className = 'writing-review writing-classroom';
  root.textContent = '';
  noteBox = el('p', {role: 'status'});
  root.appendChild(el('h1', {text: data.title || '作文课'}));
  root.appendChild(noteBox);

  if (data.teacher) {
    var topBar = el('div', {class: 'wr-top-links'});
    topBar.appendChild(el('a', {href: '/v1/weekend?s=' + sid, text: '点名、课堂计时与班级控制'}));
    if (data.status === 'planned') {
      topBar.appendChild(button('立即开始', function() {
        return api('/teacher/weekend/sessions/' + sid + '/start', {json: {}}).then(loadClass);
      }, 'primary'));
    }
    root.appendChild(topBar);
    var stageBar = el('div', {class: 'wr-class-stages'});
    (data.stages || []).forEach(function(stage) {
      stageBar.appendChild(button(stage.name, function() {
        return api('/teacher/weekend/sessions/' + sid + '/goto', {json: {stage: stage.no}}).then(loadClass);
      }, stage.no === data.stage ? 'primary' : ''));
    });
    root.appendChild(stageBar);
  }

  root.appendChild(el('p', {
    class: 'wr-intro',
    text: '当前第 ' + data.stage + ' 环节。' + (data.teacher ? '可一键开放本环节，或逐项勾选后保存开放范围；学生接口只返回开放内容。' : '只显示老师开放的内容。')
  }));

  var selected = (data.open || []).slice();
  var choose = el('select', {'aria-label': '查看环节'});
  var cards = el('div', {class: 'wr-class-cards'});
  (data.stages || []).forEach(function(stage) {
    choose.appendChild(el('option', {value: stage.no, text: stage.name, selected: stage.no === data.stage}));
  });
  var chooseRow = el('div', {class: 'wr-choose-row'});
  chooseRow.appendChild(el('label', {}, '查看环节 ', choose));
  if (data.teacher) {
    chooseRow.appendChild(button('开放本环节全部', function() {
      var no = Number(choose.value);
      var stageIds = (data.nodes || []).filter(function(n) { return Number(roleStage[n.role]) === no; }).map(function(n) { return n.id; });
      stageIds.forEach(function(id) { if (selected.indexOf(id) < 0) selected.push(id); });
      return api('/teacher/weekend/writing/sessions/' + sid + '/release', {
        json: {expectedRevision: data.revision, nodeIds: selected}
      }).then(function(d) { data = d; paintClass(); message('已开放本环节全部内容'); });
    }));
    chooseRow.appendChild(button('收回本环节', function() {
      var no = Number(choose.value);
      var stageIds = (data.nodes || []).filter(function(n) { return Number(roleStage[n.role]) === no; }).map(function(n) { return n.id; });
      selected = selected.filter(function(id) { return stageIds.indexOf(id) < 0; });
      return api('/teacher/weekend/writing/sessions/' + sid + '/release', {
        json: {expectedRevision: data.revision, nodeIds: selected}
      }).then(function(d) { data = d; paintClass(); message('已收回本环节开放内容'); });
    }));
  }
  root.appendChild(chooseRow);
  root.appendChild(cards);

  function drawStage() {
    cards.textContent = '';
    var no = Number(choose.value);
    cards.appendChild(renderStageContent(no, data.nodes || [], {
      emptyText: '本环节还没有开放内容。',
      renderControl: data.teacher ? function(n) {
        var check = el('input', {type: 'checkbox', checked: selected.indexOf(n.id) >= 0});
        check.onchange = function() {
          selected = selected.filter(function(x) { return x !== n.id; });
          if (check.checked) selected.push(n.id);
        };
        return el('label', {class: 'wr-open-toggle'}, check, ' 开放 ' + (roles[n.role] || '素材'));
      } : null
    }));
  }
  choose.onchange = drawStage;
  drawStage();

  if (data.teacher) {
    root.appendChild(button('保存开放范围', function() {
      return api('/teacher/weekend/writing/sessions/' + sid + '/release', {
        json: {expectedRevision: data.revision, nodeIds: selected}
      }).then(function(d) {
        data = d;
        paintClass();
        message('开放范围已保存');
      });
    }, 'primary'));
    teacherWork();
  } else {
    studentWork();
  }
}

function studentWork() {
  var area = el('section', {class: 'wr-item'});
  root.appendChild(area);
  api('/student/weekend/sessions/' + sid + '/written').then(function(d) {
    (d.questions || []).forEach(function(q) {
      var qBox = el('div', {class: 'wr-student-task'});
      var text = el('textarea', {'aria-label': '作文文字', placeholder: '也可先写提纲或正文，再拍照上传手写作文'});
      var camera = el('input', {type: 'file', accept: 'image/*', capture: 'environment', 'aria-label': '拍照或重拍'});
      var files = el('input', {type: 'file', accept: 'image/*', multiple: true, 'aria-label': '选择多张照片'});
      var preview = el('div', {class: 'wr-photo-preview'});
      var versionsHost = el('div', {class: 'wr-versions-host'});
      var queuedPhotos = [];
      text.value = q.submission ? q.submission.text : '';
      qBox.appendChild(el('h2', {text: q.stem}));
      qBox.appendChild(text);
      var uploadRow = el('div', {class: 'wr-bindings'});
      uploadRow.appendChild(el('label', {}, '拍照或重拍 ', camera));
      uploadRow.appendChild(el('label', {}, '从相册选择多张 ', files));
      qBox.appendChild(uploadRow);
      qBox.appendChild(preview);

      function renderQueue() {
        preview.textContent = '';
        queuedPhotos.forEach(function(f, idx) {
          var item = el('div', {class: 'wr-photo-thumb'});
          var url = URL.createObjectURL(f);
          item.appendChild(el('img', {
            src: url,
            alt: '待提交照片 ' + (idx + 1),
            style: 'max-width:160px;max-height:160px;object-fit:contain',
            onload: function() { URL.revokeObjectURL(url); }
          }));
          item.appendChild(button('移除', function() {
            queuedPhotos.splice(idx, 1);
            renderQueue();
          }));
          preview.appendChild(item);
        });
      }

      function addFiles(list) {
        Array.prototype.forEach.call(list || [], function(f) {
          if (queuedPhotos.length < 6) queuedPhotos.push(f);
        });
        renderQueue();
      }
      camera.onchange = function() { addFiles(camera.files); camera.value = ''; };
      files.onchange = function() { addFiles(files.files); files.value = ''; };

      qBox.appendChild(button('提交／重拍后再次提交', function() {
        if (queuedPhotos.length > 6) throw Error('一次最多6张照片');
        var fd = new FormData();
        fd.append('text', text.value);
        fd.append('revision', q.submission ? q.submission.revision : 0);
        queuedPhotos.forEach(function(f) { fd.append('photos', f); });
        return api('/student/weekend/sessions/' + sid + '/written/' + q.id, {method: 'POST', body: fd}).then(function(r) {
          q.submission = r.submission;
          queuedPhotos = [];
          renderQueue();
          message('已提交第 ' + r.versionNo + ' 版；照片不会因课堂翻页丢失');
        });
      }, 'primary'));
      qBox.appendChild(button('查看我的提交与批注', function() {
        return api('/student/weekend/sessions/' + sid + '/written/' + q.id + '/versions').then(function(r) {
          showVersions(versionsHost, r, q.id, null);
        });
      }));
      qBox.appendChild(versionsHost);
      area.appendChild(qBox);
    });
  }).catch(message);
  if (data.feedback) {
    area.appendChild(el('div', {class: 'wr-feedback-published'},
      el('h3', {text: '老师已发布反馈'}),
      el('p', {text: data.feedback.comment}),
      el('p', {text: '下一步建议：' + data.feedback.nextStep})
    ));
  }
}

function teacherWork() {
  var area = el('section', {class: 'wr-item'});
  root.appendChild(area);
  area.appendChild(el('h2', {text: '学生提交、批注与反馈'}));
  api('/teacher/weekend/sessions/' + sid + '/written').then(function(d) {
    (data.students || []).forEach(function(s) {
      var card = el('section', {class: 'wr-item'});
      card.appendChild(el('strong', {text: s.name}));
      var facts = (data.completion && data.completion[String(s.id)]) || {};
      card.appendChild(el('p', {
        text: '到课：' + (facts.attendance === true ? '已到' : facts.attendance === false ? '缺席' : '未点名') +
          '；范文/看图/技法到达：' + [facts.model, facts.picture, facts.methods].map(function(v) { return v ? '是' : '否'; }).join('/') +
          '；写作提交：' + (facts.submitted ? '已提交' : '未提交')
      }));
      [true, false].forEach(function(present) {
        card.appendChild(button(present ? '到课' : '缺席', function() {
          return api('/teacher/weekend/writing/sessions/' + sid + '/attendance', {
            json: {expectedRevision: data.revision, studentId: s.id, present: present}
          }).then(function(r) {
            data = r;
            message('点名已保存');
          });
        }));
      });
      var versionsHost = el('div', {class: 'wr-versions-host'});
      (d.questions || []).forEach(function(q) {
        card.appendChild(button('查看写作照片与版本', function() {
          return api('/teacher/weekend/sessions/' + sid + '/written/' + q.id + '/students/' + s.id + '/versions').then(function(r) {
            showVersions(versionsHost, r, q.id, s.id);
          });
        }));
      });
      card.appendChild(versionsHost);

      var draft = ((data.feedback && data.feedback[String(s.id)]) || {}).draft || {};
      var comment = el('textarea', {'aria-label': '教师评语'});
      var next = el('textarea', {'aria-label': '下一步建议', placeholder: '填写下一步修改建议'});
      comment.value = draft.comment || ('课堂记录：' + (facts.submitted ? '已提交写作任务。' : '尚未提交写作任务。'));
      next.value = draft.nextStep || '';
      card.appendChild(comment);
      card.appendChild(next);
      [false, true].forEach(function(publish) {
        card.appendChild(button(publish ? '确认发布反馈' : '保存反馈草稿', function() {
          return api('/teacher/weekend/writing/sessions/' + sid + '/feedback', {
            json: {studentId: s.id, expectedRevision: data.revision, comment: comment.value, nextStep: next.value, publish: publish}
          }).then(function(r) {
            data = r;
            message(publish ? '反馈已发布' : '草稿已保存，学生不可见');
          });
        }, publish ? 'primary' : ''));
      });
      area.appendChild(card);
    });
  }).catch(message);
}

function drawMarks(canvas, imgObj, shapes) {
  var width = Math.min(720, imgObj.width || 720);
  var height = (imgObj.height || 540) * width / (imgObj.width || 720);
  canvas.width = width;
  canvas.height = height;
  var ctx = canvas.getContext('2d');
  ctx.drawImage(imgObj, 0, 0, width, height);
  ctx.strokeStyle = '#d62828';
  ctx.fillStyle = '#d62828';
  ctx.lineWidth = 3;
  ctx.font = '18px sans-serif';
  shapes.forEach(function(s) {
    ctx.beginPath();
    if (s.kind === 'circle') {
      ctx.ellipse(s.x, s.y, Math.max(Math.abs(s.w), 5), Math.max(Math.abs(s.h), 5), 0, 0, Math.PI * 2);
    } else if (s.kind === 'text') {
      ctx.fillText(s.text || '', s.x, s.y);
    } else {
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(s.x + s.w, s.y + s.h);
      var a = Math.atan2(s.h, s.w);
      var x = s.x + s.w;
      var y = s.y + s.h;
      ctx.moveTo(x - 12 * Math.cos(a - 0.5), y - 12 * Math.sin(a - 0.5));
      ctx.lineTo(x, y);
      ctx.lineTo(x - 12 * Math.cos(a + 0.5), y - 12 * Math.sin(a + 0.5));
    }
    ctx.stroke();
  });
}

function showVersions(host, result, qid, student) {
  host.textContent = '';
  var list = result.items || result.versions || [];
  if (!list.length) {
    host.appendChild(el('p', {class: 'wr-empty', text: '暂无提交记录。'}));
    return;
  }
  list.forEach(function(v) {
    var box = el('section', {class: 'wr-item'});
    box.appendChild(el('p', {text: '第 ' + v.versionNo + ' 版 ' + (v.text || v.answerText || '')}));
    var shapes = [];
    var redrawFns = [];
    var mode = el('select', {'aria-label': '批注工具'});
    [['circle', '圈画'], ['arrow', '箭头'], ['text', '文字']].forEach(function(x) {
      mode.appendChild(el('option', {value: x[0], text: x[1]}));
    });
    var label = el('input', {'aria-label': '图上文字', placeholder: '文字批注'});
    if (student) {
      var bar = el('div', {class: 'wr-bindings'});
      bar.appendChild(mode);
      bar.appendChild(label);
      bar.appendChild(button('撤销上一笔', function() {
        shapes.pop();
        redrawFns.forEach(function(fn) { fn(); });
      }));
      bar.appendChild(button('清空本版批注', function() {
        shapes.length = 0;
        redrawFns.forEach(function(fn) { fn(); });
      }));
      box.appendChild(bar);
    }

    (v.photos || []).forEach(function(p, index) {
      var canvas = el('canvas', {'aria-label': '照片批注画布', style: 'max-width:100%;touch-action:none;border:1px solid #dbe3ed;border-radius:8px'});
      var start = null;
      var previewShape = null;
      var imgObj = new Image();
      var loaded = false;
      box.appendChild(canvas);
      var prior = [];
      (v.annotations || []).forEach(function(a) {
        (a.shapes || []).forEach(function(s) {
          if ((s.photoIndex || 0) === index) prior.push(s);
        });
      });

      function draw() {
        if (!loaded) return;
        var current = prior.concat(shapes.filter(function(s) { return s.photoIndex === index; }));
        if (previewShape) current = current.concat([previewShape]);
        drawMarks(canvas, imgObj, current);
      }
      redrawFns.push(draw);
      imgObj.onload = function() { loaded = true; draw(); };
      imgObj.src = p.dataUrl;

      if (student) {
        function point(e) {
          var t = (e.touches && e.touches[0]) || (e.changedTouches && e.changedTouches[0]) || e;
          var r = canvas.getBoundingClientRect();
          return {
            x: (t.clientX - r.left) * canvas.width / (r.width || 1),
            y: (t.clientY - r.top) * canvas.height / (r.height || 1)
          };
        }
        function down(e) {
          e.preventDefault();
          start = point(e);
          previewShape = null;
        }
        function move(e) {
          if (!start) return;
          e.preventDefault();
          var cur = point(e);
          previewShape = {kind: mode.value, photoIndex: index, x: start.x, y: start.y, w: cur.x - start.x, h: cur.y - start.y, text: label.value};
          draw();
        }
        function up(e) {
          if (!start) return;
          e.preventDefault();
          var end = point(e);
          shapes.push({kind: mode.value, photoIndex: index, x: start.x, y: start.y, w: end.x - start.x, h: end.y - start.y, text: label.value});
          start = null;
          previewShape = null;
          draw();
        }
        canvas.addEventListener('mousedown', down);
        canvas.addEventListener('mousemove', move);
        canvas.addEventListener('mouseup', up);
        canvas.addEventListener('touchstart', down);
        canvas.addEventListener('touchmove', move);
        canvas.addEventListener('touchend', up);
      }
    });

    (v.annotations || []).forEach(function(a) {
      var vText = verdictLabels[a.verdict] || a.verdict || '';
      box.appendChild(el('p', {class: 'wr-annotation-note', text: vText + '：' + (a.comment || '')}));
    });

    if (student) {
      var comment = el('textarea', {'aria-label': '批注文字', placeholder: '输入批注评语'});
      var verdict = el('select', {'aria-label': '批注结论'});
      [['passed', '通过'], ['needs_revision', '需修改'], ['retake', '需重拍']].forEach(function(x) {
        verdict.appendChild(el('option', {value: x[0], text: x[1]}));
      });
      box.appendChild(comment);
      box.appendChild(verdict);
      box.appendChild(button('保存批注', function() {
        return api('/teacher/weekend/sessions/' + sid + '/written/' + qid + '/students/' + student + '/annotate', {
          json: {submissionVersionId: v.id, verdict: verdict.value, comment: comment.value, shapes: shapes}
        }).then(function() {
          message('批注已保存');
          return api('/teacher/weekend/sessions/' + sid + '/written/' + qid + '/students/' + student + '/versions').then(function(r) {
            showVersions(host, r, qid, student);
          });
        });
      }, 'primary'));
    }
    host.appendChild(box);
  });
}

obtainToken().then(function(t) {
  TOKEN = t;
  if (query.get('student')) {
    root.className = 'writing-review';
    root.textContent = '';
    return api('/parent/weekend/writing/students/' + query.get('student')).then(function(d) {
      root.appendChild(el('h1', {text: '作文课已发布反馈'}));
      (d.items || []).forEach(function(i) {
        var v = i.versions[i.versions.length - 1];
        root.appendChild(el('section', {class: 'wr-item'},
          el('h2', {text: i.title}),
          el('p', {text: v.comment}),
          el('p', {text: '下一步：' + v.nextStep})
        ));
      });
    });
  }
  if (!sid && !lid) {
    root.className = 'writing-review';
    root.textContent = '';
    return api('/parent/weekend/writing').then(function(d) {
      root.appendChild(el('h1', {text: '作文课已发布反馈'}));
      (d.students || []).forEach(function(s) {
        root.appendChild(el('a', {href: '/v1/weekend-writing?student=' + s.id, text: s.name + ' 的作文反馈'}));
      });
    });
  }
  return sid ? loadClass() : prepare();
}).catch(function(e) {
  root.textContent = e.message;
});
''', True, ('/v1/weekend-plan', '返回备课'))
    css = """<style id="writing-review-workbench">
#app.writing-review{max-width:1180px;margin:0 auto;padding:20px 18px 48px;color:#172b4d}
#app.writing-review h1{font-size:26px;margin:4px 0 14px}
#app.writing-review .wr-top-links{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin:8px 0 12px}
#app.writing-review .wr-title-row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:10px 0}
#app.writing-review .wr-coverage-note{color:#354a68;background:#f4f7fb;border:1px solid #dbe3ed;border-radius:10px;padding:10px 12px;margin:8px 0}
#app.writing-review .wr-intro{color:#526581;margin:0 0 14px;line-height:1.65}
#app.writing-review .wr-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:14px 0}
#app.writing-review .wr-stat,#app.writing-review .wr-stage{border:1px solid #dbe3ed;border-radius:12px;background:#fff;padding:12px 14px}
#app.writing-review .wr-stat strong{display:block;font-size:20px;margin-bottom:3px}
#app.writing-review .wr-stages{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin:12px 0 18px}
#app.writing-review .wr-stage{cursor:pointer;text-align:left;color:#17345f;min-height:72px}
#app.writing-review .wr-stage[aria-pressed="true"]{border-color:#a80d20;box-shadow:inset 0 0 0 1px #a80d20;background:#fff8f7}
#app.writing-review .wr-stage small{display:block;color:#66758b;margin-top:5px}
#app.writing-review .wr-tools{border:1px solid #dbe3ed;border-radius:12px;background:#f7f9fc;padding:12px;margin:14px 0}
#app.writing-review .wr-tools summary{cursor:pointer;font-weight:700}
#app.writing-review .wr-tools .row{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
#app.writing-review .wr-stage-panel{border:1px solid #dbe3ed;border-radius:14px;background:#fff;padding:18px;margin:14px 0}
#app.writing-review .wr-stage-content{display:flex;flex-direction:column;gap:14px;margin:12px 0}
#app.writing-review .wr-model-pair{border:1px solid #e5ecf4;border-radius:12px;padding:14px 16px;background:#fcfdff}
#app.writing-review .wr-model-pair.has-media{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(240px,1fr);gap:16px;align-items:start}
#app.writing-review .wr-model-title{font-size:20px;margin:0 0 6px;color:#102542}
#app.writing-review .wr-model-para{margin:0;line-height:1.9;white-space:pre-wrap;font-size:16px;color:#1c2e4a}
#app.writing-review .wr-model-media{display:flex;flex-direction:column;gap:10px}
#app.writing-review .wr-figure{margin:0;padding:8px;border:1px solid #e5ecf4;border-radius:10px;background:#fff}
#app.writing-review .wr-figure img{display:block;width:100%;max-height:320px;object-fit:contain;border-radius:8px;background:#f7f8fa}
#app.writing-review .wr-figure figcaption{font-size:13px;font-weight:600;color:#4a5d7a;margin-bottom:6px}
#app.writing-review .wr-caption-text{margin:8px 0 0;line-height:1.6;color:#2c3e50}
#app.writing-review .wr-gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
#app.writing-review .wr-inline-warn{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;background:#fff4e5;border:1px solid #f5c27b;color:#7a4300;border-radius:8px;padding:8px 10px;margin-bottom:8px;font-size:13px}
#app.writing-review .wr-unbound-box{margin-top:8px}
#app.writing-review .wr-bridge{border:1px solid #e0e8f3;border-radius:12px;padding:16px;background:#fafcff}
#app.writing-review .wr-bridge h3{margin:0 0 8px}
#app.writing-review .wr-bridge-lead{color:#4a5d7a;margin:0 0 12px;line-height:1.6}
#app.writing-review .wr-method-list{padding-left:20px;margin:0 0 14px;display:flex;flex-direction:column;gap:10px}
#app.writing-review .wr-method-card{border:1px solid #e2e9f2;border-radius:10px;background:#fff;padding:10px 14px}
#app.writing-review .wr-method-text{margin:0;line-height:1.75;white-space:pre-wrap}
#app.writing-review .wr-method-img,#app.writing-review .wr-ref-img,#app.writing-review .wr-stage-img{display:block;max-width:100%;max-height:280px;object-fit:contain;margin-top:8px;border-radius:8px}
#app.writing-review .wr-method-ref{margin-top:8px;padding-top:8px;border-top:1px dashed #d7e0ec;color:#3d5370;font-size:14px}
#app.writing-review .wr-bridge-refs{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin:12px 0}
#app.writing-review .wr-bridge-ref-card{border:1px solid #e2e9f2;border-radius:10px;background:#fff;padding:12px}
#app.writing-review .wr-bridge-ref-card h4,#app.writing-review .wr-transfer-box h4{margin:0 0 8px;font-size:15px;color:#17345f}
#app.writing-review .wr-mini-gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px}
#app.writing-review .wr-mini-gallery img{width:100%;max-height:140px;object-fit:contain;border-radius:6px;background:#f7f8fa}
#app.writing-review .wr-transfer-box{border-left:4px solid #a80d20;background:#fff8f7;padding:10px 14px;border-radius:8px}
#app.writing-review .wr-transfer-box p{margin:0;line-height:1.65}
#app.writing-review .wr-stage-card{border:1px solid #e5ecf4;border-radius:10px;padding:14px;background:#fcfdff}
#app.writing-review .wr-open-toggle{display:inline-flex;align-items:center;gap:6px;font-size:13px;font-weight:600;color:#17345f;margin-bottom:8px}
#app.writing-review .wr-class-stages,#app.writing-review .wr-choose-row,#app.writing-review .wr-preview-nav,#app.writing-review .wr-preview-pager{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:10px 0}
#app.writing-review .wr-photo-preview{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0}
#app.writing-review .wr-photo-thumb{border:1px solid #dbe3ed;border-radius:8px;padding:6px;background:#fff;text-align:center}
#app.writing-review .wr-edit-drawer{margin-top:14px;border-top:1px solid #e5ecf4;padding-top:10px}
#app.writing-review .wr-edit-drawer summary{cursor:pointer;font-weight:600;color:#17345f}
#app.writing-review .wr-item{margin:10px 0;padding:16px;border:1px solid #dbe3ed;border-radius:14px;background:white}
#app.writing-review .wr-item-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap}
#app.writing-review .wr-item img{display:block;max-width:min(100%,760px);max-height:420px;object-fit:contain;margin:12px auto;border-radius:10px;background:#f7f8fa}
#app.writing-review .wr-item textarea{display:block;width:100%;min-height:100px;box-sizing:border-box;margin:10px 0;padding:10px;border:1px solid #cbd5e1;border-radius:9px;font:inherit}
#app.writing-review select,#app.writing-review input:not([type=checkbox]):not([type=file]){max-width:100%;padding:9px 10px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;font:inherit}
#app.writing-review button{margin:4px;padding:9px 13px;border:1px solid #d5dce6;border-radius:9px;background:#fff;color:#17345f;font:inherit;cursor:pointer}
#app.writing-review button.primary{background:#a80d20;color:white;border-color:#a80d20}
#app.writing-review .wr-source{color:#65748b;font-size:13px;overflow-wrap:anywhere}
#app.writing-review .wr-bindings{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0;align-items:center}
#app.writing-review .wr-bindings label{padding:8px 10px;border:1px solid #e0e6ed;border-radius:8px;max-width:100%}
#app.writing-review .wr-bindings input{margin-right:7px}
#app.writing-review .wr-annotation-note{padding:8px 10px;background:#f8fafc;border-left:3px solid #a80d20;border-radius:6px;margin:6px 0}
#app.writing-review.writing-preview{max-width:1360px}
#app.writing-review.writing-preview .wr-preview-stage{border:1px solid #dbe3ed;border-radius:16px;background:#fff;padding:24px 28px;margin:14px 0;box-shadow:0 6px 24px rgba(23,43,77,.06)}
#app.writing-review.writing-preview .wr-model-para{font-size:20px;line-height:2}
@media(max-width:760px){
  #app.writing-review{padding:14px 12px 32px}
  #app.writing-review .wr-summary{grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}
  #app.writing-review .wr-stat{padding:9px 7px;font-size:13px}
  #app.writing-review .wr-stat strong{font-size:17px}
  #app.writing-review .wr-stages{grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}
  #app.writing-review .wr-stage{padding:10px;min-height:65px}
  #app.writing-review .wr-model-pair.has-media{grid-template-columns:1fr}
}
</style>"""
    return html.replace('</head>', css + '</head>', 1)
