// adminの追加・変更フォームで、未保存入力の破棄を確認する。
(() => {
  'use strict';

  // 破棄リンクごとに、移動前の確認ダイアログを設定する。
  function initializeDiscardLinks() {
    document.querySelectorAll('[data-discard-form]').forEach((link) => {
      link.addEventListener('click', (event) => {
        if (!window.confirm('入力内容は保存されません。破棄しますか？')) {
          event.preventDefault();
        }
      });
    });
  }

  document.addEventListener('DOMContentLoaded', initializeDiscardLinks);
})();
