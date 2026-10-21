/* Local, feature-checked shims. ES5 syntax so this runs before application JS. */
(function () {
  'use strict';
  function define(object, name, value) {
    if (!object[name]) Object.defineProperty(object, name, {value: value, configurable: true, writable: true});
  }
  define(Object, 'fromEntries', function (entries) {
    var result = {};
    Array.from(entries).forEach(function (pair) {
      Object.defineProperty(result, pair[0], {value: pair[1], enumerable: true, configurable: true, writable: true});
    });
    return result;
  });
  define(Object, 'hasOwn', function (object, key) { return Object.prototype.hasOwnProperty.call(object, key); });
  define(String.prototype, 'replaceAll', function (search, replacement) {
    if (search instanceof RegExp) {
      if (!search.global) throw new TypeError('replaceAll requires a global regexp');
      return String(this).replace(search, replacement);
    }
    return String(this).replace(new RegExp(String(search).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), replacement);
  });
  define(String.prototype, 'matchAll', function (regexp) {
    var re = new RegExp(regexp.source || String(regexp), (regexp.flags || '').replace(/g/g, '')+'g');
    var value = String(this), found, result = [];
    while ((found = re.exec(value))) { result.push(found); if (!found[0]) re.lastIndex++; }
    return result[Symbol.iterator]();
  });
  define(Array.prototype, 'at', function (index) { var n = Math.trunc(Number(index) || 0); return this[n < 0 ? this.length+n : n]; });
  define(String.prototype, 'at', function (index) { var s = String(this), n = Math.trunc(Number(index) || 0); return s[n < 0 ? s.length+n : n]; });
  define(Array.prototype, 'flat', function (depth) {
    var out = [], level = depth === undefined ? 1 : Number(depth);
    this.forEach(function (value) { if (Array.isArray(value) && level > 0) out.push.apply(out, Array.prototype.flat.call(value, level-1)); else out.push(value); });
    return out;
  });
  define(Array.prototype, 'flatMap', function (fn, receiver) { return this.map(fn, receiver).flat(); });
  define(Promise, 'allSettled', function (values) {
    return Promise.all(Array.from(values).map(function (value) { return Promise.resolve(value).then(function (result) { return {status:'fulfilled', value:result}; }, function (reason) { return {status:'rejected', reason:reason}; }); }));
  });
  if (window.crypto && window.crypto.getRandomValues) define(window.crypto, 'randomUUID', function () {
    var bytes = new Uint8Array(16); window.crypto.getRandomValues(bytes); bytes[6] = (bytes[6]&15)|64; bytes[8] = (bytes[8]&63)|128;
    return Array.from(bytes).map(function (b, i) { return ([4,6,8,10].indexOf(i)>=0?'-':'')+('0'+b.toString(16)).slice(-2); }).join('');
  });
  define(window, 'structuredClone', function (value) {
    var seen = new Map();
    function clone(item) {
      if (!item || typeof item !== 'object') { if (typeof item === 'function') throw new TypeError('Cannot clone functions'); return item; }
      if (seen.has(item)) return seen.get(item);
      if (item instanceof Date) return new Date(item.getTime());
      if (item instanceof Blob) return item.slice(0, item.size, item.type);
      if (item instanceof ArrayBuffer) return item.slice(0);
      if (ArrayBuffer.isView(item)) return new item.constructor(clone(item.buffer), item.byteOffset, item.length);
      var result = Array.isArray(item) ? [] : item instanceof Map ? new Map() : item instanceof Set ? new Set() : {};
      seen.set(item, result);
      if (item instanceof Map) item.forEach(function (v,k) { result.set(clone(k),clone(v)); });
      else if (item instanceof Set) item.forEach(function (v) { result.add(clone(v)); });
      else Object.keys(item).forEach(function (key) { Object.defineProperty(result,key,{value:clone(item[key]),enumerable:true,writable:true,configurable:true}); });
      return result;
    }
    return clone(value);
  });
  if (window.Element) define(window.Element.prototype, 'replaceChildren', function () {
    while (this.firstChild) this.removeChild(this.firstChild);
    for (var i=0;i<arguments.length;i++) this.appendChild(typeof arguments[i] === 'string' ? document.createTextNode(arguments[i]) : arguments[i]);
  });
  /* Safari 12 has no SubmitEvent.submitter. Keep the existing login handler. */
  document.addEventListener('click', function (event) {
    var target = event.target.closest && event.target.closest('button,input[type=submit]');
    if (target && target.form && target.type === 'submit') target.form.__cySubmitter = target;
  }, true);
  document.addEventListener('submit', function (event) {
    if (!event.submitter) {
      var form = event.target, button = form.__cySubmitter || form.querySelector('button[type=submit],input[type=submit],button:not([type])');
      try { Object.defineProperty(event, 'submitter', {value:button}); } catch (_) {}
      form.__cySubmitter = null;
    }
  }, true);
  /* Native dialog is absent on iOS 12. Existing modal()/closeModal() still run. */
  var nativeDialog = document.createElement('dialog');
  if (typeof nativeDialog.showModal !== 'function') {
    function prepare(dialog) {
      if (dialog.showModal) return;
      var backdrop, focus, scroll, bodyStyle;
      dialog.showModal = function () {
        if (dialog.hasAttribute('open')) return;
        focus = document.activeElement; scroll = window.pageYOffset; bodyStyle = document.body.style.cssText;
        backdrop = document.createElement('div'); backdrop.className='cy-safari12-backdrop';
        backdrop.addEventListener('touchmove',function (event) { event.preventDefault(); },{passive:false});
        document.body.appendChild(backdrop); dialog.setAttribute('open','');
        document.body.style.position='fixed'; document.body.style.top=(-scroll)+'px'; document.body.style.width='100%';
        var field = dialog.querySelector('input,textarea,button,select'); if (field) field.focus();
      };
      dialog.close = function (value) {
        if (!dialog.hasAttribute('open')) return;
        dialog.removeAttribute('open'); dialog.returnValue=value || '';
        if (backdrop) backdrop.remove();
        document.body.style.cssText=bodyStyle; window.scrollTo(0,scroll);
        dialog.dispatchEvent(new Event('close'));
        if (focus && document.contains(focus)) focus.focus();
      };
      Object.defineProperty(dialog,'open',{get:function () { return dialog.hasAttribute('open'); }});
    }
    function dialogs(root) { if (root.nodeType !== 1) return; if (root.tagName === 'DIALOG') prepare(root); Array.prototype.forEach.call(root.querySelectorAll('dialog'),prepare); }
    var observer = new MutationObserver(function (records) { records.forEach(function (record) { Array.prototype.forEach.call(record.addedNodes,dialogs); }); });
    observer.observe(document.documentElement,{childList:true,subtree:true});
    document.addEventListener('DOMContentLoaded',function () { dialogs(document.documentElement); });
  }
  /* Report initialization failures instead of leaving an unexplained blank body. */
  function report() {
    var screen=document.getElementById('screen');
    if (!screen || screen.textContent.trim() || document.getElementById('cy-compat-error')) return;
    var message=document.createElement('p');message.id='cy-compat-error';message.setAttribute('role','alert');
    message.textContent='页面初始化未完成，请刷新重试。若仍只有页头，请将当前页面地址反馈给老师。';
    message.style.cssText='padding:24px;color:#8b1a1a;background:white';screen.appendChild(message);
  }
  window.addEventListener('error',function () { setTimeout(report,0); });
  window.addEventListener('unhandledrejection',function () { setTimeout(report,0); });
})();
