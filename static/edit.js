/* 共享编辑组件 VflowEdit.open({ path, name, onRenamed, onMoved, onChanged })
 * 标签增删、改名、移动、新建文件夹、全部 API 调用在此;主页面与播放页行为一致。
 */
(function () {
  'use strict';

  var ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return ESC[c]; });
  }

  var ICON = {
    close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><line x1="6" y1="6" x2="18" y2="18"></line><line x1="18" y1="6" x2="6" y2="18"></line></svg>',
    back: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 6 9 12 15 18"></polyline></svg>',
    folder: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>',
    move: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 9l-3 3 3 3"/><path d="M9 5l3-3 3 3"/><path d="M15 19l-3 3-3-3"/><path d="M19 9l3 3-3 3"/><path d="M2 12h20"/><path d="M12 2v20"/></svg>',
    trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>'
  };

  function toast(msg, kind) {
    document.querySelectorAll('.vf-edit__toast').forEach(function (e) { e.remove(); });
    var t = document.createElement('div');
    t.className = 'vf-edit__toast' + (kind === 'ok' ? ' vf-edit__toast--ok' : '');
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(function () { t.remove(); }, 2600);
  }

  function api(url, opts) {
    return fetch(url, opts).then(function (r) {
      return r.json().catch(function () { return null; }).then(function (data) {
        return { ok: r.ok, status: r.status, data: data };
      });
    });
  }
  function post(url, body) {
    return api(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  }

  function open(opts) {
    opts = opts || {};
    var path = opts.path, name = opts.name;
    var onRenamed = opts.onRenamed, onMoved = opts.onMoved, onChanged = opts.onChanged, onDelete = opts.onDelete;
    var tags = [], allTagNames = [];

    var ov = document.createElement('div');
    ov.className = 'vf-edit';
    document.body.appendChild(ov);

    document.addEventListener('keydown', onKey);
    renderMain();

    function onKey(e) {
      if (e.key === 'Escape') close();
    }
    function close() {
      document.removeEventListener('keydown', onKey);
      ov.remove();
    }

    // ---------- 主面板 ----------
    function renderMain() {
      ov.innerHTML =
        '<div class="vf-edit__panel">' +
          '<div class="vf-edit__head">' +
            '<span class="vf-edit__title">编辑<span class="vf-edit__sub">' + esc(shortName(name)) + '</span></span>' +
            '<button class="vf-edit__x" aria-label="关闭">' + ICON.close + '</button>' +
          '</div>' +
          '<div class="vf-edit__body">' +
            '<div class="vf-edit__sec">' +
              '<div class="vf-edit__label">名称</div>' +
              '<div class="vf-edit__field">' +
                '<input class="vf-edit__input" id="vf-name" type="text" value="' + esc(name) + '" autocomplete="off">' +
                '<button class="vf-edit__btn vf-edit__btn--primary" id="vf-name-save">保存</button>' +
              '</div>' +
            '</div>' +
            '<div class="vf-edit__sec">' +
              '<div class="vf-edit__label">标签<span class="hint">回车 / 逗号 添加</span></div>' +
              '<div class="vf-edit__chips" id="vf-chips"></div>' +
              '<div class="vf-edit__ac">' +
                '<input class="vf-edit__input" id="vf-tag-input" type="text" placeholder="输入标签名" autocomplete="off">' +
                '<div class="vf-edit__ac-list" id="vf-ac"></div>' +
              '</div>' +
            '</div>' +
            '<div class="vf-edit__sec">' +
              '<div class="vf-edit__label">位置</div>' +
              '<button class="vf-edit__btn vf-edit__btn--block" id="vf-move">' + ICON.move + '<span>移动到…</span></button>' +
            '</div>' +
            '<div class="vf-edit__sec">' +
              '<button class="vf-edit__btn vf-edit__btn--block vf-edit__btn--danger" id="vf-del">' + ICON.trash + '<span>删除视频</span></button>' +
            '</div>' +
          '</div>' +
        '</div>';

      ov.querySelector('.vf-edit__x').onclick = close;
      ov.querySelector('#vf-name-save').onclick = saveName;
      ov.querySelector('#vf-name').addEventListener('keydown', function (e) {
        if (e.key === 'Enter') { e.preventDefault(); saveName(); }
      });
      ov.querySelector('#vf-move').onclick = renderMove;
      ov.querySelector('#vf-del').onclick = doDelete;
      wireTagInput();
      load();
    }

    async function load() {
      var m = await api('/api/meta?path=' + encodeURIComponent(path));
      var t = await api('/api/tags');
      if (m.ok && m.data) tags = m.data.tags || [];
      if (t.ok && Array.isArray(t.data)) allTagNames = t.data.map(function (x) { return x.name; });
      renderChips();
    }

    // ---- 名称(改名)----
    async function saveName() {
      var val = ov.querySelector('#vf-name').value.trim();
      if (!val) { toast('名称不能为空'); return; }
      if (val === name) { close(); return; }
      var r = await post('/api/rename', { path: path, new_name: val });
      if (!r.ok) { toast((r.data && r.data.error) || '改名失败'); return; }
      toast('已重命名', 'ok');
      close();
      if (onRenamed) onRenamed(r.data.path, r.data.name);
    }

    // ---- 标签 ----
    function renderChips() {
      var box = ov.querySelector('#vf-chips');
      if (!box) return;
      box.innerHTML = tags.map(function (t) {
        return '<span class="vf-edit__chip">' + esc(t) +
          '<button data-tag="' + esc(t) + '" aria-label="删除标签">×</button></span>';
      }).join('');
      box.querySelectorAll('button').forEach(function (b) {
        b.onclick = function () { removeTag(b.getAttribute('data-tag')); };
      });
    }

    function wireTagInput() {
      var input = ov.querySelector('#vf-tag-input');
      var list = ov.querySelector('#vf-ac');
      input.addEventListener('input', function () { showAc(input.value); });
      input.addEventListener('focus', function () { showAc(input.value); });
      input.addEventListener('blur', function () { setTimeout(function () { list.innerHTML = ''; }, 150); });
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ',') {
          e.preventDefault();
          if (addTag(input.value)) input.value = '';
          list.innerHTML = '';
        }
      });
      function showAc(q) {
        q = q.trim().toLowerCase();
        if (!q) { list.innerHTML = ''; return; }
        var hits = allTagNames.filter(function (n) {
          return n.toLowerCase().indexOf(q) === 0 && !tags.some(function (x) { return x.toLowerCase() === n.toLowerCase(); });
        }).slice(0, 6);
        list.innerHTML = hits.map(function (n) {
          return '<button class="vf-edit__ac-item" data-name="' + esc(n) + '">' + esc(n) + '</button>';
        }).join('');
        list.querySelectorAll('.vf-edit__ac-item').forEach(function (it) {
          it.onmousedown = function () {
            if (addTag(it.getAttribute('data-name'))) input.value = '';
            list.innerHTML = '';
          };
        });
      }
    }

    function addTag(raw) {
      var t = (raw || '').trim();
      if (!t) return false;
      if (tags.some(function (x) { return x.toLowerCase() === t.toLowerCase(); })) return false;
      saveTags(tags.concat([t]));
      return true;
    }
    function removeTag(t) {
      saveTags(tags.filter(function (x) { return x !== t; }));
    }
    async function saveTags(list) {
      var r = await post('/api/tags', { path: path, tags: list });
      if (!r.ok) { toast((r.data && r.data.error) || '保存失败'); load(); return; }
      tags = list.slice();
      renderChips();
      if (onChanged) onChanged(tags.slice());
    }

    // ---- 删除 ----
    async function doDelete() {
      if (!window.confirm('确定删除「' + name + '」?此操作不可恢复。')) return;
      var r = await post('/api/delete', { path: path });
      if (!r.ok) { toast((r.data && r.data.error) || '删除失败'); return; }
      toast('已删除', 'ok');
      close();
      if (onDelete) onDelete();
    }

    // ---------- 移动视图(内嵌文件夹浏览器)----------
    function renderMove() {
      var cur = parentOf(path); // 默认从当前视频所在文件夹开始浏览
      ov.innerHTML =
        '<div class="vf-edit__panel">' +
          '<div class="vf-edit__head">' +
            '<button class="vf-edit__back" aria-label="返回">' + ICON.back + '</button>' +
            '<span class="vf-edit__title">移动到…</span>' +
            '<button class="vf-edit__x" aria-label="关闭">' + ICON.close + '</button>' +
          '</div>' +
          '<div class="vf-edit__body">' +
            '<div class="vf-edit__crumbs" id="vf-mcrumbs"></div>' +
            '<div class="vf-edit__folders" id="vf-mlist"></div>' +
            '<div class="vf-edit__newdir">' +
              '<input class="vf-edit__input" id="vf-newdir" type="text" placeholder="在此新建文件夹" autocomplete="off">' +
              '<button class="vf-edit__btn" id="vf-newdir-btn">新建</button>' +
            '</div>' +
            '<button class="vf-edit__btn vf-edit__btn--primary vf-edit__btn--block" id="vf-move-ok">移动到此文件夹</button>' +
          '</div>' +
        '</div>';

      ov.querySelector('.vf-edit__back').onclick = renderMain;
      ov.querySelector('.vf-edit__x').onclick = close;
      ov.querySelector('#vf-move-ok').onclick = confirmMove;
      ov.querySelector('#vf-newdir-btn').onclick = makeDir;
      ov.querySelector('#vf-newdir').addEventListener('keydown', function (e) {
        if (e.key === 'Enter') { e.preventDefault(); makeDir(); }
      });
      refresh();

      function setC(p) { cur = p; refresh(); }

      async function refresh() {
        renderCrumbs();
        var r = await api('/api/browse?path=' + encodeURIComponent(cur));
        var dirs = (r.ok && r.data && r.data.dirs) || [];
        var el = ov.querySelector('#vf-mlist');
        el.innerHTML = dirs.length
          ? dirs.map(function (d) {
              return '<button class="vf-edit__folder" data-p="' + esc(d.path) + '">' + ICON.folder + '<span>' + esc(d.name) + '</span></button>';
            }).join('')
          : '<div class="vf-edit__empty">没有子文件夹</div>';
        el.querySelectorAll('.vf-edit__folder').forEach(function (b) {
          b.onclick = function () { setC(b.getAttribute('data-p')); };
        });
      }
      function renderCrumbs() {
        var parts = cur ? cur.split('/') : [];
        var html = '<button class="vf-edit__crumb" data-p="">根目录</button>';
        for (var i = 0; i < parts.length; i++) {
          var p = parts.slice(0, i + 1).join('/');
          var last = i === parts.length - 1;
          html += '<span class="vf-edit__sep">/</span>';
          html += '<button class="vf-edit__crumb"' + (last ? ' aria-current="page"' : '') + ' data-p="' + esc(p) + '">' + esc(parts[i]) + '</button>';
        }
        var cel = ov.querySelector('#vf-mcrumbs');
        cel.innerHTML = html;
        cel.querySelectorAll('.vf-edit__crumb').forEach(function (b) {
          b.onclick = function () { setC(b.getAttribute('data-p')); };
        });
      }
      async function makeDir() {
        var nm = ov.querySelector('#vf-newdir').value.trim();
        if (!nm) return;
        var target = cur ? cur + '/' + nm : nm;
        var r = await post('/api/mkdir', { path: target });
        if (!r.ok) { toast((r.data && r.data.error) || '新建失败'); return; }
        toast('已新建文件夹', 'ok');
        ov.querySelector('#vf-newdir').value = '';
        refresh();
      }
      async function confirmMove() {
        var r = await post('/api/move', { path: path, dest_dir: cur });
        if (!r.ok) { toast((r.data && r.data.error) || '移动失败'); return; }
        toast('已移动', 'ok');
        close();
        if (onMoved) onMoved(r.data.path, r.data.name);
      }
    }

    return { close: close };
  }

  function parentOf(rel) {
    rel = String(rel || '').replace(/\\/g, '/');
    var i = rel.lastIndexOf('/');
    return i < 0 ? '' : rel.slice(0, i);
  }
  function shortName(s) {
    s = String(s || '');
    return s.length > 24 ? s.slice(0, 22) + '…' : s;
  }

  window.VflowEdit = { open: open };
})();
